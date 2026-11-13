//! Validation of the tagged-dict tree into IR (port of `schema.py`).
//!
//! Every message, code, and path matches Python, and so does the order in
//! which fields are checked: the first error wins, so the evaluation order of
//! Python's constructor arguments is reproduced deliberately (e.g. a split's
//! `axis` is checked after its children, a component's `metadata` contents
//! after its body). The parity test in `tests/test_rust_schema_parity.py`
//! fuzzes this against the Python implementation.

use std::fmt::Write;

use crate::ir::{AssemblyBlock, BuildMetadata, Component, EntitySpec, Node, Phase, SizeExpr, ValidatorSpec, MAX_STAGE};
use crate::model::{Axis, BlockSpec, BlockState, BuildError, Diagnostic, Point, Region, Rotation, SourceRef};
use crate::val::{Dict, Val};

type R<T> = Result<T, BuildError>;

/// A JSON-path-like location (`$.body.children[3]`), rendered only on error
/// so the happy path does no string building.
#[derive(Clone, Copy)]
enum Path<'a> {
    Root,
    Key(&'a Path<'a>, &'a str),
    Index(&'a Path<'a>, usize),
}

impl<'a> Path<'a> {
    fn key(&'a self, key: &'a str) -> Path<'a> {
        Path::Key(self, key)
    }

    fn index(&'a self, index: usize) -> Path<'a> {
        Path::Index(self, index)
    }

    fn render(&self) -> String {
        let mut out = String::new();
        self.write(&mut out);
        out
    }

    fn write(&self, out: &mut String) {
        match self {
            Path::Root => out.push('$'),
            Path::Key(parent, key) => {
                parent.write(out);
                out.push('.');
                out.push_str(key);
            }
            Path::Index(parent, i) => {
                parent.write(out);
                let _ = write!(out, "[{i}]");
            }
        }
    }
}

fn error(path: &Path, message: impl Into<String>) -> BuildError {
    error_code(path, message, "invalid_ir")
}

fn error_code(path: &Path, message: impl Into<String>, code: &'static str) -> BuildError {
    Diagnostic::new(code, message, path.render()).into()
}

fn dict<'v>(value: &'v Val, path: &Path) -> R<&'v Dict> {
    match value {
        Val::Dict(d) => Ok(d),
        _ => Err(error(path, "expected an object")),
    }
}

fn keys(obj: &Dict, required: &[&str], optional: &[&str], path: &Path) -> R<()> {
    let mut missing: Vec<&str> = required.iter().copied().filter(|k| !obj.contains_key(*k)).collect();
    if !missing.is_empty() {
        missing.sort_unstable();
        return Err(error(path, format!("missing fields: {}", missing.join(", "))));
    }
    let mut unknown: Vec<&str> = obj
        .keys()
        .map(String::as_str)
        .filter(|k| !required.contains(k) && !optional.contains(k))
        .collect();
    if !unknown.is_empty() {
        unknown.sort_unstable();
        return Err(error(path, format!("unknown fields: {}", unknown.join(", "))));
    }
    Ok(())
}

/// `obj.get(key)` followed by `is not None`.
fn present<'v>(obj: &'v Dict, key: &str) -> Option<&'v Val> {
    obj.get(key).filter(|v| !v.is_null())
}

/// Field known to exist because `keys()` checked it as required.
fn field<'v>(obj: &'v Dict, key: &str) -> &'v Val {
    &obj[key]
}

fn int(value: &Val, path: &Path, minimum: Option<i64>) -> R<i32> {
    let Val::Int(v) = value else {
        return Err(error(path, "expected an integer"));
    };
    if let Some(minimum) = minimum {
        if *v < minimum {
            return Err(error(path, format!("expected an integer >= {minimum}")));
        }
    }
    // Deliberate narrowing (Python ints are unbounded): coordinates and
    // extents are stored as i32, matching NBT's Int tags.
    i32::try_from(*v).map_err(|_| error(path, "expected an integer between -2147483648 and 2147483647"))
}

fn point(value: &Val, path: &Path, positive: bool) -> R<Point> {
    let Val::List(items) = value else {
        return Err(error(path, "expected a three-integer coordinate"));
    };
    if items.len() != 3 {
        return Err(error(path, "expected a three-integer coordinate"));
    }
    let minimum = positive.then_some(1);
    let x = int(&items[0], &path.index(0), minimum)?;
    let y = int(&items[1], &path.index(1), minimum)?;
    let z = int(&items[2], &path.index(2), minimum)?;
    Ok(Point::new(x, y, z))
}

fn region(value: &Val, path: &Path) -> R<Region> {
    let obj = dict(value, path)?;
    keys(obj, &["min", "max"], &[], path)?;
    let min = point(field(obj, "min"), &path.key("min"), false)?;
    let max = point(field(obj, "max"), &path.key("max"), false)?;
    Region::new(min, max).map_err(|message| error(path, message))
}

fn axis(value: &Val, path: &Path) -> R<Axis> {
    value.as_str().and_then(Axis::parse).ok_or_else(|| error(path, "axis must be x, y, or z"))
}

/// `IDENTIFIER = ^[a-z0-9_.-]+:[a-z0-9_./-]+$`, applied with `fullmatch`.
fn is_identifier(value: &str) -> bool {
    let Some((namespace, name)) = value.split_once(':') else {
        return false;
    };
    let ns_ok = |c: u8| c.is_ascii_lowercase() || c.is_ascii_digit() || matches!(c, b'_' | b'.' | b'-');
    !namespace.is_empty()
        && !name.is_empty()
        && namespace.bytes().all(ns_ok)
        && name.bytes().all(|c| ns_ok(c) || c == b'/')
}

fn identifier(value: &Val, path: &Path) -> R<String> {
    match value.as_str() {
        Some(s) if is_identifier(s) => Ok(s.to_owned()),
        _ => Err(error(path, "expected a namespaced Minecraft identifier")),
    }
}

fn block(value: &Val, path: &Path) -> R<BlockSpec> {
    let obj = dict(value, path)?;
    keys(obj, &["block_type"], &["block_state", "nbt"], path)?;
    let block_type = identifier(field(obj, "block_type"), &path.key("block_type"))?;
    let block_state = match obj.get("block_state") {
        None => BlockState::new(),
        Some(Val::Dict(state)) => {
            let mut out = BlockState::with_capacity(state.len());
            for (k, v) in state {
                match v {
                    Val::Str(s) => {
                        out.insert(k.clone(), s.clone());
                    }
                    _ => return Err(error(&path.key("block_state"), "expected a string-to-string object")),
                }
            }
            out
        }
        Some(_) => return Err(error(&path.key("block_state"), "expected a string-to-string object")),
    };
    let block_nbt = match present(obj, "nbt") {
        None => None,
        Some(nbt @ Val::Dict(_)) => Some(nbt_dict(nbt, &path.key("nbt"))?),
        Some(_) => return Err(error(&path.key("nbt"), "expected an object of block-entity data")),
    };
    Ok(BlockSpec { block_type, block_state, block_nbt })
}

/// Like props, but NBT has no null, so `None` is rejected everywhere.
fn nbt_value(value: &Val, path: &Path) -> R<()> {
    match value {
        Val::Float(f) if !f.is_finite() => Err(error(path, "nbt numbers must be finite")),
        Val::Str(_) | Val::Bool(_) | Val::Int(_) | Val::Float(_) => Ok(()),
        Val::List(items) => {
            for (i, item) in items.iter().enumerate() {
                nbt_value(item, &path.index(i))?;
            }
            Ok(())
        }
        Val::Dict(map) => {
            for (k, v) in map {
                nbt_value(v, &path.key(k))?;
            }
            Ok(())
        }
        Val::Null => Err(error(path, "nbt must contain only strings, numbers, booleans, lists, and objects")),
    }
}

fn nbt_dict(value: &Val, path: &Path) -> R<Dict> {
    nbt_value(value, path)?;
    match value {
        Val::Dict(d) => Ok(d.clone()),
        _ => unreachable!("callers pass a dict"),
    }
}

fn number(value: &Val, path: &Path) -> R<f64> {
    match value {
        Val::Int(i) => Ok(*i as f64),
        Val::Float(f) if f.is_finite() => Ok(*f),
        _ => Err(error(path, "expected a finite number")),
    }
}

const RESERVED_ENTITY_FIELDS: [&str; 4] = ["Pos", "Rotation", "UUID", "id"]; // sorted

fn entity(value: &Val, path: &Path) -> R<EntitySpec> {
    let obj = dict(value, path)?;
    keys(obj, &["entity_type"], &["nbt", "yaw", "pitch"], path)?;
    let entity_type = identifier(field(obj, "entity_type"), &path.key("entity_type"))?;
    let nbt = match present(obj, "nbt") {
        None => None,
        Some(raw) => {
            let nbt_path = path.key("nbt");
            let map = dict(raw, &nbt_path)?;
            let reserved: Vec<&str> = RESERVED_ENTITY_FIELDS.iter().copied().filter(|k| map.contains_key(*k)).collect();
            if !reserved.is_empty() {
                return Err(error(&nbt_path, format!("reserved entity fields: {}", reserved.join(", "))));
            }
            Some(nbt_dict(raw, &nbt_path)?)
        }
    };
    let zero = Val::Int(0);
    let yaw = number(obj.get("yaw").unwrap_or(&zero), &path.key("yaw"))?;
    let pitch = number(obj.get("pitch").unwrap_or(&zero), &path.key("pitch"))?;
    if !(-90.0..=90.0).contains(&pitch) {
        return Err(error(&path.key("pitch"), "pitch must be between -90 and 90"));
    }
    Ok(EntitySpec { entity_type, nbt, yaw, pitch })
}

fn source(value: &Val, path: &Path) -> R<SourceRef> {
    let obj = dict(value, path)?;
    keys(obj, &["file"], &["line", "column"], path)?;
    let file = field(obj, "file").as_str().ok_or_else(|| error(&path.key("file"), "expected a string"))?;
    let line = present(obj, "line").map(|v| int(v, &path.key("line"), Some(1))).transpose()?;
    let column = present(obj, "column").map(|v| int(v, &path.key("column"), Some(1))).transpose()?;
    Ok(SourceRef { file: file.to_owned(), line, column })
}

fn metadata(value: &Val, path: &Path) -> R<BuildMetadata> {
    let obj = dict(value, path)?;
    let mut unknown: Vec<&str> = obj.keys().map(String::as_str).filter(|k| !matches!(*k, "ground_level" | "stage_delay_ticks")).collect();
    if !unknown.is_empty() {
        unknown.sort_unstable();
        return Err(error_code(path, format!("unknown metadata fields: {}", unknown.join(", ")), "invalid_metadata"));
    }
    let ground_level = match obj.get("ground_level") {
        None => 0,
        Some(Val::Int(v)) if *v >= 0 => i32::try_from(*v).map_err(|_| {
            error_code(&path.key("ground_level"), "expected a non-negative integer", "invalid_metadata")
        })?,
        Some(_) => {
            return Err(error_code(&path.key("ground_level"), "expected a non-negative integer", "invalid_metadata"))
        }
    };
    let stage_delay_ticks = match obj.get("stage_delay_ticks") {
        None | Some(Val::Null) => None,
        Some(Val::Int(v)) if (1..=100).contains(v) => Some(*v as i32),
        Some(_) => {
            return Err(error_code(&path.key("stage_delay_ticks"), "expected an integer from 1 to 100", "invalid_metadata"))
        }
    };
    Ok(BuildMetadata { ground_level, stage_delay_ticks })
}

fn validator(value: &Val, path: &Path) -> R<ValidatorSpec> {
    let obj = dict(value, path)?;
    let kind = obj.get("kind");
    if kind.and_then(Val::as_str) == Some("door_supported_on_both_sides") {
        keys(obj, &["kind", "assembly"], &[], path)?;
        return match field(obj, "assembly") {
            Val::Str(s) if !s.is_empty() => Ok(ValidatorSpec::DoorSupportedOnBothSides { assembly: s.clone() }),
            _ => Err(error_code(&path.key("assembly"), "expected a non-empty string", "invalid_validator")),
        };
    }
    let shown = kind.map_or_else(|| "None".to_owned(), Val::py_repr);
    Err(error_code(path, format!("unknown validator kind {shown}"), "invalid_validator"))
}

fn size_expr(value: &Val, path: &Path) -> R<SizeExpr> {
    let obj = dict(value, path)?;
    let kind = obj.get("kind");
    match kind.and_then(Val::as_str) {
        Some("fixed") => {
            keys(obj, &["kind", "value"], &[], path)?;
            Ok(SizeExpr::Fixed(int(field(obj, "value"), &path.key("value"), Some(1))?))
        }
        Some("fill") => {
            keys(obj, &["kind"], &[], path)?;
            Ok(SizeExpr::Fill)
        }
        _ => {
            let shown = kind.map_or_else(|| "None".to_owned(), Val::py_repr);
            Err(error(path, format!("unknown size expression kind {shown}")))
        }
    }
}

fn phase(obj: &Dict, path: &Path) -> R<Phase> {
    match obj.get("phase").map(Val::as_str) {
        None | Some(Some("structure")) => Ok(Phase::Structure),
        Some(Some("fixture")) => Ok(Phase::Fixture),
        Some(_) => Err(error(&path.key("phase"), "phase must be structure or fixture")),
    }
}

fn stage(obj: &Dict, path: &Path) -> R<u8> {
    match present(obj, "stage") {
        None => Ok(0),
        Some(Val::Int(v)) if (0..=i64::from(MAX_STAGE)).contains(v) => Ok(*v as u8),
        Some(_) => Err(error_code(&path.key("stage"), format!("stage must be an integer from 0 to {MAX_STAGE}"), "invalid_stage")),
    }
}

fn rotation(value: &Val, path: &Path) -> R<Rotation> {
    let degrees = int(value, path, None)?;
    Rotation::from_degrees(degrees.into()).ok_or_else(|| error(path, "expected 0, 90, 180, or 270"))
}

fn children(value: &Val, path: &Path, source_file: Option<&str>) -> R<Vec<Node>> {
    match value {
        Val::List(items) => items.iter().enumerate().map(|(i, v)| node(v, &path.index(i), source_file)).collect(),
        _ => unreachable!("callers check for a list"),
    }
}

/// Parse and validate the tree returned by the Starlark entry function.
/// `source_file` becomes the `SourceRef` of components that carry none.
pub fn parse_node(value: &Val, source_file: Option<&str>) -> R<Node> {
    node(value, &Path::Root, source_file)
}

fn node(value: &Val, path: &Path, source_file: Option<&str>) -> R<Node> {
    let obj = dict(value, path)?;
    let Some(kind) = obj.get("kind").and_then(Val::as_str) else {
        return Err(error(path, "missing string field 'kind'"));
    };
    match kind {
        "component" => {
            keys(obj, &["kind", "name", "props", "body"], &["min_size", "source", "metadata", "validators"], path)?;
            let name = match field(obj, "name") {
                Val::Str(s) if !s.is_empty() => s.clone(),
                _ => return Err(error(&path.key("name"), "expected a non-empty string")),
            };
            let props = dict(field(obj, "props"), &path.key("props"))?.clone();
            let source = match obj.get("source") {
                Some(raw) if raw.truthy() => Some(source(raw, &path.key("source"))?),
                _ => source_file.map(SourceRef::file),
            };
            let raw_metadata = present(obj, "metadata");
            if raw_metadata.is_some() && !matches!(path, Path::Root) {
                return Err(error_code(&path.key("metadata"), "metadata is only allowed on the root component", "metadata_not_root"));
            }
            let validators = match obj.get("validators") {
                None => Vec::new(),
                Some(Val::List(items)) => {
                    let vpath = path.key("validators");
                    items.iter().enumerate().map(|(i, v)| validator(v, &vpath.index(i))).collect::<R<Vec<_>>>()?
                }
                Some(_) => return Err(error_code(&path.key("validators"), "expected a list", "invalid_validator")),
            };
            // Python builds Component(...) with these arguments in this order.
            let body = node(field(obj, "body"), &path.key("body"), source_file)?;
            let min_size = present(obj, "min_size").map(|v| point(v, &path.key("min_size"), true)).transpose()?;
            let metadata = raw_metadata.map(|v| metadata(v, &path.key("metadata"))).transpose()?;
            Ok(Node::Component(Box::new(Component { name, props, body, min_size, source, metadata, validators })))
        }
        "group" => {
            keys(obj, &["kind", "children"], &[], path)?;
            let raw = field(obj, "children");
            if !matches!(raw, Val::List(_)) {
                return Err(error(&path.key("children"), "expected a list"));
            }
            Ok(Node::Group { children: children(raw, &path.key("children"), source_file)? })
        }
        "split" => {
            keys(obj, &["kind", "axis", "sizes", "children"], &[], path)?;
            let (Val::List(raw_sizes), raw_children @ Val::List(child_items)) = (field(obj, "sizes"), field(obj, "children")) else {
                return Err(error(path, "sizes and children must be lists"));
            };
            let spath = path.key("sizes");
            let sizes = raw_sizes.iter().enumerate().map(|(i, v)| size_expr(v, &spath.index(i))).collect::<R<Vec<_>>>()?;
            let kids = children(raw_children, &path.key("children"), source_file)?;
            if sizes.is_empty() || sizes.len() != child_items.len() {
                return Err(error(path, "split requires equal, non-empty sizes and children"));
            }
            let axis = axis(field(obj, "axis"), &path.key("axis"))?;
            Ok(Node::Split { axis, sizes, children: kids })
        }
        "inset" => {
            keys(obj, &["kind", "amounts", "child"], &[], path)?;
            let apath = path.key("amounts");
            let amounts_obj = dict(field(obj, "amounts"), &apath)?;
            keys(amounts_obj, &["x", "y", "z"], &[], &apath)?;
            let mut amounts = [(0, 0); 3];
            for axis in Axis::ALL {
                match &amounts_obj[axis.as_str()] {
                    // Python reports pair element errors at the node path.
                    Val::List(pair) if pair.len() == 2 => {
                        amounts[axis.index()] = (int(&pair[0], path, Some(0))?, int(&pair[1], path, Some(0))?);
                    }
                    _ => return Err(error(&apath.key(axis.as_str()), "expected [low, high]")),
                }
            }
            let child = node(field(obj, "child"), &path.key("child"), source_file)?;
            Ok(Node::Inset { amounts, child: Box::new(child) })
        }
        "repeat" => {
            keys(obj, &["kind", "axis", "count", "child_extent", "gap", "child"], &[], path)?;
            let axis = axis(field(obj, "axis"), &path.key("axis"))?;
            let count = int(field(obj, "count"), &path.key("count"), Some(1))?;
            let child_extent = int(field(obj, "child_extent"), &path.key("child_extent"), Some(1))?;
            let gap = int(field(obj, "gap"), &path.key("gap"), Some(0))?;
            let child = node(field(obj, "child"), &path.key("child"), source_file)?;
            Ok(Node::Repeat { axis, count, child_extent, gap, child: Box::new(child) })
        }
        "at" => {
            keys(obj, &["kind", "pos", "child", "rotation"], &["size"], path)?;
            let child = node(field(obj, "child"), &path.key("child"), source_file)?;
            let size = match obj.get("size") {
                Some(raw) => Some(point(raw, &path.key("size"), true)?),
                None => child.min_size(),
            };
            let Some(child_size) = size else {
                return Err(error_code(
                    path,
                    "at requires size=[width, height, length] or a child component with min_size",
                    "missing_component_size",
                ));
            };
            let rotation = rotation(field(obj, "rotation"), &path.key("rotation"))?;
            let translation = point(field(obj, "pos"), &path.key("pos"), false)?;
            Ok(Node::Transform { translation, rotation, child_size, child: Box::new(child) })
        }
        "transform" => {
            keys(obj, &["kind", "translation", "rotation_y", "child_size", "child"], &[], path)?;
            let rotation = rotation(field(obj, "rotation_y"), &path.key("rotation_y"))?;
            let translation = point(field(obj, "translation"), &path.key("translation"), false)?;
            let child_size = point(field(obj, "child_size"), &path.key("child_size"), true)?;
            let child = node(field(obj, "child"), &path.key("child"), source_file)?;
            Ok(Node::Transform { translation, rotation, child_size, child: Box::new(child) })
        }
        "place_block" => {
            keys(obj, &["kind", "pos", "block"], &["phase", "stage"], path)?;
            let phase = phase(obj, path)?;
            let stage = stage(obj, path)?;
            let pos = point(field(obj, "pos"), &path.key("pos"), false)?;
            let block = block(field(obj, "block"), &path.key("block"))?;
            Ok(Node::PlaceBlock { pos, block, phase, stage })
        }
        "place_entity" => {
            keys(obj, &["kind", "pos", "entity"], &[], path)?;
            let pos = point(field(obj, "pos"), &path.key("pos"), false)?;
            let entity = entity(field(obj, "entity"), &path.key("entity"))?;
            Ok(Node::PlaceEntity { pos, entity })
        }
        "fill_region" => {
            keys(obj, &["kind", "box", "block"], &["phase", "stage"], path)?;
            let phase = phase(obj, path)?;
            let stage = stage(obj, path)?;
            let region = region(field(obj, "box"), &path.key("box"))?;
            let block = block(field(obj, "block"), &path.key("block"))?;
            Ok(Node::FillRegion { region, block, phase, stage })
        }
        "carve_region" => {
            keys(obj, &["kind", "box"], &["stage"], path)?;
            let stage = stage(obj, path)?;
            Ok(Node::CarveRegion { region: region(field(obj, "box"), &path.key("box"))?, stage })
        }
        "place_assembly" => {
            keys(obj, &["kind", "pos", "name", "size", "blocks"], &["stage"], path)?;
            let stage = stage(obj, path)?;
            let name = match field(obj, "name") {
                Val::Str(s) if !s.is_empty() => s.clone(),
                _ => return Err(error(&path.key("name"), "expected a non-empty string")),
            };
            let bpath = path.key("blocks");
            let items = match field(obj, "blocks") {
                Val::List(items) if !items.is_empty() => items,
                _ => return Err(error(&bpath, "expected a non-empty list")),
            };
            let mut blocks = Vec::with_capacity(items.len());
            for (i, raw) in items.iter().enumerate() {
                let item_path = bpath.index(i);
                let item = dict(raw, &item_path)?;
                keys(item, &["pos", "block"], &[], &item_path)?;
                blocks.push(AssemblyBlock {
                    pos: point(field(item, "pos"), &item_path.key("pos"), false)?,
                    block: block(field(item, "block"), &item_path.key("block"))?,
                });
            }
            let pos = point(field(obj, "pos"), &path.key("pos"), false)?;
            let size = point(field(obj, "size"), &path.key("size"), true)?;
            Ok(Node::PlaceAssembly { pos, name, size, blocks, stage })
        }
        other => Err(error(path, format!("unknown node kind {}", crate::val::py_str_repr(other)))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::val::from_json;

    fn parse(json: &str) -> R<Node> {
        parse_node(&from_json(json), None)
    }

    fn err(json: &str) -> (String, String, String) {
        let e = parse(json).expect_err("expected a schema error");
        let d = &e.diagnostics[0];
        (d.code.to_owned(), d.component_path.clone(), d.message.clone())
    }

    const STONE: &str = r#"{"block_type": "minecraft:stone"}"#;

    // Ported from tests/test_schema_layout.py.
    #[test]
    fn rejects_unknown_fields_and_bool_coordinates() {
        assert_eq!(err(r#"{"kind": "group", "children": [], "surprise": 1}"#).2, "unknown fields: surprise");
        let e = err(&format!(r#"{{"kind": "place_block", "pos": [true, 0, 0], "block": {STONE}}}"#));
        assert_eq!((e.1.as_str(), e.2.as_str()), ("$.pos[0]", "expected an integer"));
    }

    #[test]
    fn root_component_parses_typed_metadata() {
        let n = parse(&format!(r#"{{"kind": "component", "name": "Embedded", "props": {{}}, "min_size": [1, 2, 1],
            "metadata": {{"ground_level": 1}}, "body": {{"kind": "place_block", "pos": [0, 0, 0], "block": {STONE}}}}}"#)).unwrap();
        let Node::Component(c) = n else { panic!() };
        assert_eq!(c.metadata, Some(BuildMetadata { ground_level: 1, stage_delay_ticks: None }));
        assert_eq!(c.metadata.unwrap().y_offset(), -1);
    }

    #[test]
    fn rejects_invalid_metadata() {
        for metadata in [r#"{"ground_level": true}"#, r#"{"ground_level": -1}"#, r#"{"surprise": 1}"#] {
            let e = err(&format!(r#"{{"kind": "component", "name": "Invalid", "props": {{}}, "metadata": {metadata},
                "body": {{"kind": "group", "children": []}}}}"#));
            assert_eq!(e.0, "invalid_metadata", "{metadata}");
        }
    }

    #[test]
    fn parses_stages_and_stage_delay() {
        let n = parse(&format!(r#"{{"kind": "component", "name": "S", "props": {{}}, "metadata": {{"stage_delay_ticks": 5}},
            "body": {{"kind": "place_block", "pos": [0, 0, 0], "block": {STONE}, "stage": 7}}}}"#)).unwrap();
        let Node::Component(c) = n else { panic!() };
        assert_eq!(c.metadata.unwrap().stage_delay_ticks, Some(5));
        assert!(matches!(c.body, Node::PlaceBlock { stage: 7, .. }));
        let carve = parse(r#"{"kind": "carve_region", "box": {"min": [0, 0, 0], "max": [1, 1, 1]}, "stage": 2}"#).unwrap();
        assert!(matches!(carve, Node::CarveRegion { stage: 2, .. }));
        for stage in ["-1", "64", "true", "\"1\""] {
            let e = err(&format!(r#"{{"kind": "place_block", "pos": [0, 0, 0], "block": {STONE}, "stage": {stage}}}"#));
            assert_eq!((e.0.as_str(), e.1.as_str()), ("invalid_stage", "$.stage"), "{stage}");
        }
        for ticks in ["0", "101", "true"] {
            let e = err(&format!(r#"{{"kind": "component", "name": "S", "props": {{}}, "metadata": {{"stage_delay_ticks": {ticks}}},
                "body": {{"kind": "group", "children": []}}}}"#));
            assert_eq!(e.0, "invalid_metadata", "{ticks}");
        }
    }

    #[test]
    fn rejects_metadata_on_nested_components() {
        let e = err(r#"{"kind": "component", "name": "Root", "props": {}, "body": {
            "kind": "component", "name": "Nested", "props": {}, "metadata": {"ground_level": 1},
            "body": {"kind": "group", "children": []}}}"#);
        assert_eq!((e.0.as_str(), e.1.as_str()), ("metadata_not_root", "$.body.metadata"));
    }

    #[test]
    fn parses_typed_validators() {
        let n = parse(r#"{"kind": "component", "name": "V", "props": {}, "validators": [
            {"kind": "door_supported_on_both_sides", "assembly": "entrance_door"}],
            "body": {"kind": "group", "children": []}}"#).unwrap();
        let Node::Component(c) = n else { panic!() };
        assert_eq!(c.validators, vec![ValidatorSpec::DoorSupportedOnBothSides { assembly: "entrance_door".into() }]);
    }

    #[test]
    fn rejects_invalid_validators() {
        for validators in [
            r#"{"kind": "door_supported_on_both_sides", "assembly": "door"}"#,
            r#"[{"kind": "unknown", "assembly": "door"}]"#,
            r#"[{"kind": "door_supported_on_both_sides", "assembly": ""}]"#,
        ] {
            let e = err(&format!(r#"{{"kind": "component", "name": "I", "props": {{}}, "validators": {validators},
                "body": {{"kind": "group", "children": []}}}}"#));
            assert_eq!(e.0, "invalid_validator", "{validators}");
        }
        let e = err(r#"{"kind": "component", "name": "I", "props": {}, "validators": [{"kind": "unknown"}],
            "body": {"kind": "group", "children": []}}"#);
        assert_eq!(e.2, "unknown validator kind 'unknown'");
    }

    #[test]
    fn block_accepts_nested_nbt_and_rejects_invalid_payloads() {
        let n = parse(r#"{"kind": "place_block", "pos": [0, 0, 0], "block": {"block_type": "minecraft:oak_sign",
            "nbt": {"front_text": {"messages": ["hi", "", "", ""], "has_glowing_text": true}}}}"#).unwrap();
        let Node::PlaceBlock { block, .. } = n else { panic!() };
        assert!(block.block_nbt.is_some());
        let e = err(r#"{"kind": "place_block", "pos": [0, 0, 0], "block": {"block_type": "minecraft:oak_sign", "nbt": ["not", "an", "object"]}}"#);
        assert_eq!(e.2, "expected an object of block-entity data");
        let e = err(r#"{"kind": "place_block", "pos": [0, 0, 0], "block": {"block_type": "minecraft:oak_sign", "nbt": {"front_text": null}}}"#);
        assert_eq!((e.1.as_str(), e.2.as_str()), ("$.block.nbt.front_text", "nbt must contain only strings, numbers, booleans, lists, and objects"));
    }

    #[test]
    fn identifiers_follow_the_python_regex() {
        for ok in ["minecraft:stone", "my-mod.x:a/b_c-1.d"] {
            assert!(is_identifier(ok), "{ok}");
        }
        for bad in ["Stone", "minecraft:", ":stone", "a:b:c", "minecraft:Stone", "minecraft:stone\n", "a/b:c"] {
            assert!(!is_identifier(bad), "{bad}");
        }
    }

    #[test]
    fn first_error_follows_python_evaluation_order() {
        // Split: children are parsed before the axis is checked.
        let e = err(r#"{"kind": "split", "axis": "w", "sizes": [{"kind": "fill"}], "children": [{"kind": "nope"}]}"#);
        assert_eq!((e.1.as_str(), e.2.as_str()), ("$.children[0]", "unknown node kind 'nope'"));
        // at: child, then size, then rotation, then pos.
        let e = err(r#"{"kind": "at", "pos": "bad", "rotation": 45, "child": {"kind": "group", "children": []}, "size": [1, 1, 1]}"#);
        assert_eq!((e.1.as_str(), e.2.as_str()), ("$.rotation", "expected 0, 90, 180, or 270"));
        let e = err(r#"{"kind": "at", "pos": [0, 0, 0], "rotation": 0, "child": {"kind": "group", "children": []}}"#);
        assert_eq!(e.0, "missing_component_size");
        // Inset pair element errors are reported at the node path.
        let e = err(r#"{"kind": "inset", "amounts": {"x": [-1, 0], "y": [0, 0], "z": [0, 0]}, "child": {"kind": "group", "children": []}}"#);
        assert_eq!((e.1.as_str(), e.2.as_str()), ("$", "expected an integer >= 0"));
    }

    #[test]
    fn region_and_entity_messages() {
        let e = err(r#"{"kind": "carve_region", "box": {"min": [0, 0, 0], "max": [0, 1, 1]}}"#);
        assert_eq!(e.2, "box must have positive extents: Box(min=Point(x=0, y=0, z=0), max=Point(x=0, y=1, z=1))");
        let e = err(r#"{"kind": "place_entity", "pos": [0, 0, 0], "entity": {"entity_type": "minecraft:pig", "nbt": {"UUID": 1, "id": "x"}}}"#);
        assert_eq!((e.1.as_str(), e.2.as_str()), ("$.entity.nbt", "reserved entity fields: UUID, id"));
        let e = err(r#"{"kind": "place_entity", "pos": [0, 0, 0], "entity": {"entity_type": "minecraft:pig", "pitch": 91}}"#);
        assert_eq!(e.2, "pitch must be between -90 and 90");
        let e = err(r#"{"kind": "place_block", "pos": [0, 0, 4294967296], "block": {"block_type": "minecraft:stone"}}"#);
        assert_eq!((e.1.as_str(), e.2.as_str()), ("$.pos[2]", "expected an integer between -2147483648 and 2147483647"));
    }

    #[test]
    fn to_val_matches_python_jsonable_shape() {
        let n = parse(r#"{"kind": "inset", "amounts": {"x": [1, 1], "y": [0, 0], "z": [0, 0]}, "child": {"kind": "group", "children": []}}"#).unwrap();
        assert_eq!(n.to_val().py_repr(),
            "{'kind': 'Inset', 'amounts': {'Axis.X': [1, 1], 'Axis.Y': [0, 0], 'Axis.Z': [0, 0]}, 'child': {'kind': 'Group', 'children': []}}");
    }
}
