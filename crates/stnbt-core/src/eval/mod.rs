//! Starlark evaluation in Rust (port of `starlark_runtime.py`).
//!
//! It uses the same engine as starlark-pyo3 (facebook/starlark-rust), with
//! the Standard dialect and Standard globals that starlark-pyo3 uses by
//! default, plus:
//! - the tree constructors (`prelude.star`) and the nbt helpers
//!   (`helpers.star`), evaluated once into a frozen module that every
//!   module imports;
//! - the math builtins (`natives.rs`), as globals.
//!
//! `load()` resolves relative to the loading file. With a `loader_root`,
//! loads are confined to its `lib/` directory and to named mounts, and every
//! confinement failure reads "module not found" so `load()` can't probe the
//! filesystem. The first loader failure is reported as itself (`load_error`
//! / `load_cycle`, path `<load>`), not as the Starlark error wrapping it.
//!
//! Results convert to `Val` as starlark-pyo3's marshalling did: tuples
//! become lists and non-finite floats become `None`. Unlike it, non-string
//! dict keys are rejected here (the corpus never uses them).

mod natives;

use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;

use starlark::environment::{FrozenModule, Globals, GlobalsBuilder, Module};
use starlark::eval::{Evaluator, FileLoader};
use starlark::syntax::{AstModule, Dialect};
use starlark::values::dict::{AllocDict, DictRef};
use starlark::values::float::StarlarkFloat;
use starlark::values::list::{AllocList, ListRef};
use starlark::values::tuple::TupleRef;
use starlark::values::{Heap, UnpackValue, Value};

use crate::model::{BuildError, Diagnostic, SourceRef};
use crate::val::{py_str_repr, Dict, Val};

const PRELUDE: &str = include_str!("prelude.star");
const HELPERS: &str = include_str!("helpers.star");

fn globals() -> &'static Globals {
    static GLOBALS: OnceLock<Globals> = OnceLock::new();
    GLOBALS.get_or_init(|| GlobalsBuilder::standard().with(natives::math_builtins).build())
}

/// The constructors and helpers, frozen once per process.
fn prelude() -> &'static FrozenModule {
    static PRELUDE_MODULE: OnceLock<FrozenModule> = OnceLock::new();
    PRELUDE_MODULE.get_or_init(|| {
        let source = format!("{PRELUDE}\n{HELPERS}");
        let ast = AstModule::parse("<prelude>", source, &Dialect::Standard).expect("prelude parses");
        Module::with_temp_heap(|module| {
            Evaluator::new(&module).eval_module(ast, globals()).expect("prelude evaluates");
            module.freeze().expect("prelude freezes")
        })
    })
}

/// Where `load()` may look.
#[derive(Clone, Debug, Default)]
pub struct LoadOptions {
    /// Directory relative loads resolve from. Defaults to `loader_root`.
    pub base_dir: Option<PathBuf>,
    /// Confines loads to `<root>/lib` and the mounts.
    pub loader_root: Option<PathBuf>,
    /// Extra top-level names under the root, mapped to outside directories
    /// (e.g. `library` for `../library/<name>/v1.star`).
    pub mounts: Vec<(String, PathBuf)>,
}

/// `Path.resolve(strict=False)`: absolute, `..` collapsed, and symlinks
/// resolved for the part of the path that exists.
fn resolve(path: &Path) -> PathBuf {
    let mut lexical = PathBuf::new();
    for component in path.components() {
        match component {
            Component::ParentDir => {
                lexical.pop();
            }
            Component::CurDir => {}
            other => lexical.push(other),
        }
    }
    let mut existing = lexical.clone();
    let mut rest = Vec::new();
    while !existing.exists() {
        match existing.file_name() {
            Some(name) => {
                rest.push(name.to_owned());
                existing.pop();
            }
            None => break,
        }
    }
    let mut out = existing.canonicalize().unwrap_or(existing);
    for name in rest.iter().rev() {
        out.push(name);
    }
    out
}

enum Mounted {
    NotAMount,
    Escapes,
    At(PathBuf),
}

struct Loader {
    base_dir: PathBuf,
    dir_stack: RefCell<Vec<PathBuf>>,
    root: Option<PathBuf>,
    allowed: &'static [&'static str],
    mounts: Vec<(String, PathBuf)>,
    cache: RefCell<HashMap<String, FrozenModule>>,
    in_progress: RefCell<HashSet<String>>,
    /// The first loader failure, re-raised as itself after evaluation fails.
    error: RefCell<Option<BuildError>>,
}

impl Loader {
    fn new(base_dir: PathBuf, opts: &LoadOptions) -> Loader {
        Loader {
            dir_stack: RefCell::new(vec![base_dir.clone()]),
            base_dir,
            root: opts.loader_root.as_deref().map(resolve),
            allowed: &["lib"],
            mounts: opts.mounts.iter().map(|(name, path)| (name.clone(), resolve(path))).collect(),
            cache: RefCell::default(),
            in_progress: RefCell::default(),
            error: RefCell::default(),
        }
    }

    fn fail(&self, code: &'static str, message: String, file: &str) -> BuildError {
        let error: BuildError = Diagnostic::new(code, message, "<load>").with_source(Some(SourceRef::file(file))).into();
        self.error.borrow_mut().get_or_insert_with(|| error.clone());
        error
    }

    fn mounted(&self, resolved: &Path) -> Mounted {
        let Some(root) = &self.root else { return Mounted::NotAMount };
        let Ok(relative) = resolved.strip_prefix(root) else { return Mounted::NotAMount };
        let mut parts = relative.components();
        let Some(first) = parts.next() else { return Mounted::NotAMount };
        let Some((_, mount)) = self.mounts.iter().find(|(name, _)| first.as_os_str() == name.as_str()) else {
            return Mounted::NotAMount;
        };
        let real = resolve(&mount.join(parts.as_path()));
        if real.starts_with(mount) && &real != mount { Mounted::At(real) } else { Mounted::Escapes }
    }

    fn permitted(&self, resolved: &Path) -> bool {
        let Some(root) = &self.root else { return true };
        match resolved.strip_prefix(root) {
            Ok(relative) => relative.components().next().is_some_and(|c| self.allowed.iter().any(|a| c.as_os_str() == *a)),
            Err(_) => false,
        }
    }

    fn load_module(&self, path: &str) -> Result<FrozenModule, LoadFailure> {
        let raw = Path::new(path);
        let not_found = || self.fail("load_error", format!("module not found: {path}"), path);
        if self.root.is_some() && raw.is_absolute() {
            return Err(not_found().into());
        }
        let joined = if raw.is_absolute() { raw.to_path_buf() } else { self.dir_stack.borrow().last().expect("non-empty").join(raw) };
        let mut resolved = resolve(&joined);
        let mounted = match self.mounted(&resolved) {
            Mounted::Escapes => return Err(not_found().into()),
            Mounted::NotAMount if !self.permitted(&resolved) => return Err(not_found().into()),
            Mounted::NotAMount => false,
            Mounted::At(real) => {
                resolved = real;
                true
            }
        };
        let key = resolved.to_string_lossy().into_owned();
        if let Some(module) = self.cache.borrow().get(&key) {
            return Ok(module.clone());
        }
        if self.in_progress.borrow().contains(&key) {
            return Err(self.fail("load_cycle", format!("circular load of {path}"), &key).into());
        }
        let source = match std::fs::read_to_string(&resolved) {
            Ok(source) => source,
            Err(_) if self.root.is_some() => return Err(not_found().into()),
            Err(e) => return Err(self.fail("load_error", format!("cannot load {path}: {e}"), &key).into()),
        };
        self.in_progress.borrow_mut().insert(key.clone());
        self.dir_stack.borrow_mut().push(if mounted { self.base_dir.clone() } else { resolved.parent().map(Path::to_path_buf).unwrap_or_default() });
        let result = self.evaluate_library(&key, source);
        self.dir_stack.borrow_mut().pop();
        self.in_progress.borrow_mut().remove(&key);
        let frozen = result?;
        self.cache.borrow_mut().insert(key, frozen.clone());
        Ok(frozen)
    }

    fn evaluate_library(&self, key: &str, source: String) -> Result<FrozenModule, LoadFailure> {
        let ast = AstModule::parse(key, source, &Dialect::Standard).map_err(LoadFailure::Starlark)?;
        Module::with_temp_heap(|module| {
            module.import_public_symbols(prelude());
            {
                let mut eval = Evaluator::new(&module);
                eval.set_loader(self);
                eval.eval_module(ast, globals()).map_err(LoadFailure::Starlark)?;
            }
            module.freeze().map_err(|e| LoadFailure::Starlark(starlark::Error::new_other(anyhow::anyhow!("{e:?}"))))
        })
    }
}

/// A failed load: either our own diagnostic (also recorded in
/// `Loader::error`) or a Starlark error from the loaded module.
enum LoadFailure {
    Build(BuildError),
    Starlark(starlark::Error),
}

impl From<BuildError> for LoadFailure {
    fn from(e: BuildError) -> Self {
        LoadFailure::Build(e)
    }
}

impl FileLoader for Loader {
    fn load(&self, path: &str) -> starlark::Result<FrozenModule> {
        self.load_module(path).map_err(|failure| match failure {
            LoadFailure::Build(e) => starlark::Error::new_other(anyhow::anyhow!("{e}")),
            LoadFailure::Starlark(e) => e,
        })
    }
}

fn is_identifier(s: &str) -> bool {
    let mut chars = s.chars();
    chars.next().is_some_and(|c| c.is_ascii_alphabetic() || c == '_') && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

fn alloc<'v>(heap: Heap<'v>, value: &Val) -> Value<'v> {
    match value {
        Val::Null => Value::new_none(),
        Val::Bool(b) => Value::new_bool(*b),
        Val::Int(i) => heap.alloc(*i),
        Val::Float(f) => heap.alloc(*f),
        Val::Str(s) => heap.alloc(s.as_str()),
        Val::List(items) => heap.alloc(AllocList(items.iter().map(|item| alloc(heap, item)))),
        Val::Dict(map) => heap.alloc(AllocDict(map.iter().map(|(k, v)| (k.as_str(), alloc(heap, v))))),
    }
}

/// A Starlark result as a `Val`, as starlark-pyo3's marshalling produced it.
fn to_val(value: Value<'_>) -> Result<Val, String> {
    Ok(match value.get_type() {
        "NoneType" => Val::Null,
        "bool" => Val::Bool(value.unpack_bool().expect("bool")),
        "int" => Val::Int(
            i64::unpack_value(value).ok().flatten().ok_or_else(|| format!("integer {value} does not fit in 64 bits"))?,
        ),
        "float" => {
            let f = StarlarkFloat::unpack_value(value).ok().flatten().expect("float").0;
            if f.is_finite() { Val::Float(f) } else { Val::Null }
        }
        "string" => Val::Str(value.unpack_str().expect("string").to_owned()),
        "list" => Val::List(ListRef::from_value(value).expect("list").iter().map(to_val).collect::<Result<_, _>>()?),
        "tuple" => Val::List(TupleRef::from_value(value).expect("tuple").iter().map(to_val).collect::<Result<_, _>>()?),
        "dict" => {
            let dict = DictRef::from_value(value).expect("dict");
            let mut out = Dict::with_capacity(dict.len());
            for (k, v) in dict.iter() {
                let key = k.unpack_str().ok_or_else(|| format!("object keys must be strings, got {} key {k}", k.get_type()))?;
                out.insert(key.to_owned(), to_val(v)?);
            }
            Val::Dict(out)
        }
        other => return Err(format!("a {other} value cannot be part of the build tree")),
    })
}

/// Evaluate `source` and call its `entry` function with `props` as keyword
/// arguments, returning the raw tagged-dict tree.
pub fn evaluate_source(source: &str, filename: &str, entry: &str, props: &Dict, opts: &LoadOptions) -> Result<Val, BuildError> {
    let source_ref = Some(SourceRef::file(filename));
    if !is_identifier(entry) {
        return Err(Diagnostic::new("invalid_entry", format!("entry {} is not a valid identifier", py_str_repr(entry)), entry)
            .with_source(source_ref)
            .into());
    }
    let base_dir = opts.base_dir.clone().or_else(|| opts.loader_root.clone());
    let loader = base_dir.map(|dir| Loader::new(dir, opts));
    let starlark_error = |message: String| -> BuildError {
        Diagnostic::new("starlark_error", message, entry).with_source(source_ref.clone()).into()
    };

    enum Failure {
        Starlark(starlark::Error),
        Missing,
        Convert(String),
    }
    let outcome = Module::with_temp_heap(|module| -> Result<Val, Failure> {
        module.import_public_symbols(prelude());
        let ast = AstModule::parse(filename, source.to_owned(), &Dialect::Standard).map_err(Failure::Starlark)?;
        let mut eval = Evaluator::new(&module);
        if let Some(loader) = &loader {
            eval.set_loader(loader);
        }
        eval.eval_module(ast, globals()).map_err(Failure::Starlark)?;
        let function = module.get(entry).ok_or(Failure::Missing)?;
        let heap = module.heap();
        let named: Vec<(&str, Value<'_>)> = props.iter().map(|(k, v)| (k.as_str(), alloc(heap, v))).collect();
        let result = eval.eval_function(function, &[], &named).map_err(Failure::Starlark)?;
        to_val(result).map_err(Failure::Convert)
    });
    match outcome {
        Ok(tree) => Ok(tree),
        Err(Failure::Starlark(e)) => {
            if let Some(error) = loader.as_ref().and_then(|l| l.error.borrow().clone()) {
                return Err(error);
            }
            Err(starlark_error(e.to_string()))
        }
        Err(Failure::Missing) => Err(starlark_error(format!("Variable `{entry}` not found"))),
        Err(Failure::Convert(message)) => Err(Diagnostic::new("invalid_ir", message, "$").into()),
    }
}

/// `evaluate_source` on a file, resolving loads from its directory.
pub fn evaluate_file(path: &Path, entry: &str, props: &Dict) -> Result<Val, BuildError> {
    let source = std::fs::read_to_string(path).map_err(|e| {
        crate::model::fail("load_error", format!("cannot read {}: {e}", path.display()), "<root>")
    })?;
    let opts = LoadOptions { base_dir: Some(resolve(&std::env::current_dir().unwrap_or_default().join(path)).parent().map(Path::to_path_buf).unwrap_or_default()), ..LoadOptions::default() };
    evaluate_source(&source, &path.to_string_lossy(), entry, props, &opts)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn eval(source: &str) -> Result<Val, BuildError> {
        evaluate_source(source, "t.star", "build", &Dict::new(), &LoadOptions::default())
    }

    fn value(source: &str) -> String {
        eval(&format!("def build():\n    return {source}\n")).unwrap().py_repr()
    }

    fn code(r: Result<Val, BuildError>) -> &'static str {
        r.unwrap_err().diagnostics[0].code
    }

    /// A scratch directory tree, removed on drop.
    struct Tree(PathBuf);

    impl Tree {
        fn new(name: &str, files: &[(&str, &str)]) -> Tree {
            let root = std::env::temp_dir().join(format!("stnbt-eval-{name}-{}", std::process::id()));
            let _ = std::fs::remove_dir_all(&root);
            for (path, content) in files {
                let file = root.join(path);
                std::fs::create_dir_all(file.parent().unwrap()).unwrap();
                std::fs::write(file, content).unwrap();
            }
            Tree(resolve(&root))
        }
    }

    impl Drop for Tree {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn math_builtins_follow_python_semantics() {
        assert_eq!(value("[round(2.5), round(-2.5), round(7), floor(-1.5), ceil(1.2), isqrt(17), isqrt(16)]"), "[3, -3, 7, -2, 2, 4, 4]");
        assert_eq!(value("[sqrt(16), atan2(0, 1), PI > 3.14]"), "[4.0, 0.0, True]");
        assert_eq!(code(eval("def build():\n    return sqrt(-1)\n")), "starlark_error");
        assert_eq!(code(eval("def build():\n    return isqrt(-1)\n")), "starlark_error");
        assert_eq!(code(eval("def build():\n    return isqrt(2.0)\n")), "starlark_error");
    }

    #[test]
    fn prelude_constructors_and_helpers_are_available_and_shadowable() {
        assert_eq!(value(r#"block("minecraft:stone")"#), "{'block_type': 'minecraft:stone', 'block_state': {}}");
        assert_eq!(value(r#"loot_nbt("chests/x", seed = 3)"#), "{'id': 'minecraft:chest', 'LootTable': 'chests/x', 'LootTableSeed': 3}");
        assert_eq!(value(r#"container_nbt(["minecraft:apple", {"id": "minecraft:egg", "count": 2, "slot": 5}])["Items"][1]"#),
                   "{'Slot': 5, 'id': 'minecraft:egg', 'count': 2}");
        assert_eq!(value(r#"sign_nbt(["hi"])["front_text"]["messages"]"#), "['hi', '', '', '']");
        let shadowed = eval("def block(t):\n    return t\n\ndef build():\n    return block(1)\n").unwrap();
        assert_eq!(shadowed.py_repr(), "1");
    }

    #[test]
    fn entry_props_and_conversion() {
        let mut props = Dict::new();
        props.insert("name".into(), Val::Str("Named".into()));
        props.insert("n".into(), Val::Int(2));
        let tree = evaluate_source("def build(name, n):\n    return [name, n, (1, 2), 1e308 * 10]\n", "t.star", "build", &props, &LoadOptions::default()).unwrap();
        assert_eq!(tree.py_repr(), "['Named', 2, [1, 2], None]");
        assert_eq!(code(evaluate_source("def build():\n    return 1\n", "t.star", "not-valid", &Dict::new(), &LoadOptions::default())), "invalid_entry");
        assert_eq!(code(eval("def other():\n    return 1\n")), "starlark_error");
        assert_eq!(code(eval("def build():\n    return {1: 2}\n")), "invalid_ir");
        assert_eq!(code(eval("def build(:\n")), "starlark_error");
        // Standard dialect, as starlark-pyo3: no f-strings.
        assert_eq!(code(eval("def build():\n    return f'{1}'\n")), "starlark_error");
    }

    #[test]
    fn loads_resolve_relative_to_the_loading_file() {
        let t = Tree::new("relative", &[
            ("main.star", "load(\"lib/a.star\", \"A\")\ndef build():\n    return A\n"),
            ("lib/a.star", "load(\"b.star\", \"B\")\nA = B + 1\n"),
            ("lib/b.star", "B = 41\n"),
        ]);
        let source = std::fs::read_to_string(t.0.join("main.star")).unwrap();
        let opts = LoadOptions { base_dir: Some(t.0.clone()), ..LoadOptions::default() };
        assert_eq!(evaluate_source(&source, "main.star", "build", &Dict::new(), &opts).unwrap().py_repr(), "42");
        assert_eq!(evaluate_file(&t.0.join("main.star"), "build", &Dict::new()).unwrap().py_repr(), "42");
    }

    #[test]
    fn loader_reports_cycles_missing_files_and_confinement() {
        let t = Tree::new("errors", &[
            ("lib/a.star", "load(\"b.star\", \"B\")\nA = 1\n"),
            ("lib/b.star", "load(\"a.star\", \"A\")\nB = 1\n"),
            ("secret/x.star", "X = 1\n"),
            ("outside/lib/m.star", "M = 7\n"),
        ]);
        let run = |src: &str, opts: &LoadOptions| evaluate_source(src, "main.star", "build", &Dict::new(), opts);
        let free = LoadOptions { base_dir: Some(t.0.clone()), ..LoadOptions::default() };
        let e = run("load(\"lib/a.star\", \"A\")\ndef build():\n    return A\n", &free).unwrap_err();
        assert_eq!((e.diagnostics[0].code, e.diagnostics[0].component_path.as_str()), ("load_cycle", "<load>"));
        let e = run("load(\"nope.star\", \"N\")\ndef build():\n    return 1\n", &free).unwrap_err();
        assert_eq!(e.diagnostics[0].code, "load_error");
        assert!(e.diagnostics[0].message.starts_with("cannot load nope.star: "), "{}", e.diagnostics[0].message);

        let confined = LoadOptions { base_dir: Some(t.0.join("scripts")), loader_root: Some(t.0.clone()), mounts: vec![("library".into(), t.0.join("outside"))] };
        for path in ["../secret/x.star", "/etc/hosts", "../lib/missing.star", "../library/../../secret/x.star"] {
            let e = run(&format!("load(\"{path}\", \"X\")\ndef build():\n    return 1\n"), &confined).unwrap_err();
            assert_eq!((e.diagnostics[0].code, e.diagnostics[0].message.clone()), ("load_error", format!("module not found: {path}")), "{path}");
        }
        assert_eq!(run("load(\"../library/lib/m.star\", \"M\")\ndef build():\n    return M\n", &confined).unwrap().py_repr(), "7");
    }
}
