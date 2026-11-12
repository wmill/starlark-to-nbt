//! Python bindings: the `starlark_to_nbt._core` extension module.
//!
//! Kept deliberately thin — conversion between Python values and core types
//! only. Pipeline logic belongs in `stnbt-core`.

mod convert;

use pyo3::prelude::*;
use pyo3::types::PyList;
use stnbt_core::val::{Dict, Val};

/// Version of the Rust core this extension was built from.
#[pyfunction]
fn version() -> &'static str {
    stnbt_core::version()
}

/// Validate a raw tagged-dict tree with the Rust schema.
///
/// Returns `("ok", ir)` where `ir` equals Python's `_jsonable(parse_node(tree))`,
/// or `("error", [(code, component_path, message), ...])`. Used by the schema
/// parity tests; the build entry points arrive in Phase 5.
#[pyfunction]
#[pyo3(signature = (tree, source_file=None))]
fn parse_ir<'py>(py: Python<'py>, tree: &Bound<'py, PyAny>, source_file: Option<&str>) -> PyResult<(&'static str, Bound<'py, PyAny>)> {
    let value = convert::to_val(tree)?;
    match stnbt_core::schema::parse_node(&value, source_file) {
        Ok(node) => Ok(("ok", convert::from_val(py, &node.to_val())?)),
        Err(err) => {
            let items = PyList::empty(py);
            for d in &err.diagnostics {
                items.append((d.code, d.component_path.as_str(), d.message.as_str()))?;
            }
            Ok(("error", items.into_any()))
        }
    }
}

fn region_val(r: &stnbt_core::model::Region) -> Val {
    r.to_val()
}

/// Diagnostics as dicts with every field, for parity comparisons.
fn diagnostics_val(err: &stnbt_core::model::BuildError) -> Val {
    Val::List(err.diagnostics.iter().map(|d| {
        let mut m = Dict::new();
        m.insert("code".into(), Val::Str(d.code.into()));
        m.insert("component_path".into(), Val::Str(d.component_path.clone()));
        m.insert("message".into(), Val::Str(d.message.clone()));
        m.insert("region".into(), d.region.as_ref().map_or(Val::Null, region_val));
        m.insert("coordinates".into(), d.coordinates.map_or(Val::Null, |p| p.to_val()));
        m.insert("details".into(), Val::Dict(d.details.clone()));
        m.insert("source".into(), d.source.as_ref().map_or(Val::Null, |src| Val::List(vec![
            Val::Str(src.file.clone()),
            src.line.map_or(Val::Null, |l| Val::Int(l.into())),
        ])));
        Val::Dict(m)
    }).collect())
}

/// Run schema -> layout -> lowering in Rust on a raw tree.
///
/// Returns `("ok", {"resolved", "operations", "entities", "validators"})` in
/// the shape of Python's debug dumps, or `("error", [diagnostic dicts])`.
/// Used by the lowering parity tests until Phase 5 wires up real builds.
#[pyfunction]
#[pyo3(signature = (tree, root_size, source_file=None))]
fn lower_tree<'py>(py: Python<'py>, tree: &Bound<'py, PyAny>, root_size: [i32; 3], source_file: Option<&str>) -> PyResult<(&'static str, Bound<'py, PyAny>)> {
    use stnbt_core::{debug, layout, lowering, model::{Point, Region}, schema};
    let value = convert::to_val(tree)?;
    let run = || -> Result<Val, stnbt_core::model::BuildError> {
        let node = schema::parse_node(&value, source_file)?;
        let root = Region::from_size(Point::new(root_size[0], root_size[1], root_size[2]), Point::ZERO)
            .map_err(|m| stnbt_core::model::fail("invalid_box", m, "<root>"))?;
        let resolved = layout::resolve(&node, root)?;
        let lowered = lowering::lower_all(&resolved)?;
        let mut out = Dict::new();
        out.insert("resolved".into(), resolved.to_val());
        out.insert("operations".into(), debug::operations_to_val(&lowered.operations, &lowered.blocks));
        out.insert("entities".into(), debug::entities_to_val(&lowered.entities));
        out.insert("validators".into(), Val::List(lowered.validators.iter().map(|v| {
            let stnbt_core::ir::ValidatorSpec::DoorSupportedOnBothSides { assembly } = &v.validator;
            Val::List(vec![
                Val::Str(assembly.clone()),
                Val::Str(v.provenance.component_path.clone()),
                region_val(&v.provenance.assigned_region),
                Val::Int(v.sequence as i64),
            ])
        }).collect()));
        Ok(Val::Dict(out))
    };
    match run() {
        Ok(v) => Ok(("ok", convert::from_val(py, &v)?)),
        Err(e) => Ok(("error", convert::from_val(py, &diagnostics_val(&e))?)),
    }
}

/// Run schema -> layout -> lowering -> execute -> support/validators.
///
/// Returns `("ok", {"voxels", "entities", "metadata"})`, where voxels are
/// `[pos, block, component_path, phase]` in (y, z, x) order, or
/// `("error", [diagnostic dicts])`. Used by the execute parity tests.
#[pyfunction]
#[pyo3(signature = (tree, root_size, source_file=None))]
fn build_tree<'py>(py: Python<'py>, tree: &Bound<'py, PyAny>, root_size: [i32; 3], source_file: Option<&str>) -> PyResult<(&'static str, Bound<'py, PyAny>)> {
    use stnbt_core::{debug, model::{Point, Region}, pipeline, schema};
    let value = convert::to_val(tree)?;
    let run = || -> Result<Val, stnbt_core::model::BuildError> {
        let node = schema::parse_node(&value, source_file)?;
        let root = Region::from_size(Point::new(root_size[0], root_size[1], root_size[2]), Point::ZERO)
            .map_err(|m| stnbt_core::model::fail("invalid_box", m, "<root>"))?;
        let result = pipeline::finish_build(&node, root)?;
        let voxels = result.volume.sorted_points().into_iter().map(|p| {
            let v = &result.volume.voxels[&p];
            Val::List(vec![
                p.to_val(),
                debug::block_to_val(result.blocks.get(v.block)),
                Val::Str(v.provenance.component_path.clone()),
                Val::Str(v.phase.name().into()),
            ])
        }).collect();
        let mut metadata = Dict::new();
        metadata.insert("ground_level".into(), Val::Int(result.metadata.ground_level.into()));
        metadata.insert("y_offset".into(), Val::Int(result.metadata.y_offset().into()));
        let mut out = Dict::new();
        out.insert("voxels".into(), Val::List(voxels));
        out.insert("entities".into(), debug::entities_to_val(&result.volume.entities));
        out.insert("metadata".into(), Val::Dict(metadata));
        Ok(Val::Dict(out))
    };
    match run() {
        Ok(v) => Ok(("ok", convert::from_val(py, &v)?)),
        Err(e) => Ok(("error", convert::from_val(py, &diagnostics_val(&e))?)),
    }
}

/// Build a raw tree and write its outputs: the structure NBT, the
/// `.meta.json` sidecar, and with `debug_dir` the per-stage JSON.
///
/// Returns `None` on success or `("error", [diagnostic dicts])`. Used by
/// the serialization parity tests; Phase 5 replaces it with real builds.
#[pyfunction]
#[pyo3(signature = (tree, root_size, source_file, nbt_path, debug_dir=None))]
fn write_tree<'py>(py: Python<'py>, tree: &Bound<'py, PyAny>, root_size: [i32; 3], source_file: Option<&str>,
                   nbt_path: std::path::PathBuf, debug_dir: Option<std::path::PathBuf>) -> PyResult<Option<(&'static str, Bound<'py, PyAny>)>> {
    use stnbt_core::{model::{Point, Region}, pipeline, schema, serialize};
    let value = convert::to_val(tree)?;
    let run = || -> Result<(), stnbt_core::model::BuildError> {
        let node = schema::parse_node(&value, source_file)?;
        let root = Region::from_size(Point::new(root_size[0], root_size[1], root_size[2]), Point::ZERO)
            .map_err(|m| stnbt_core::model::fail("invalid_box", m, "<root>"))?;
        let result = pipeline::finish_build(&node, root)?;
        serialize::write_build_outputs(&node, &result, &nbt_path, debug_dir.as_deref())
    };
    match run() {
        Ok(()) => Ok(None),
        Err(e) => Ok(Some(("error", convert::from_val(py, &diagnostics_val(&e))?))),
    }
}

pyo3::create_exception!(
    _core,
    CoreBuildError,
    pyo3::exceptions::PyException,
    "A build failed; args[0] is the list of diagnostic dicts."
);

/// Fingerprint of the Rust sources and prelude this extension was built
/// from (see build.rs). Output caches must include it.
#[pyfunction]
fn build_fingerprint() -> &'static str {
    env!("STNBT_BUILD_FINGERPRINT")
}

fn core_error(py: Python<'_>, err: &stnbt_core::model::BuildError) -> PyErr {
    match convert::from_val(py, &diagnostics_val(err)) {
        Ok(diags) => CoreBuildError::new_err((diags.unbind(),)),
        Err(e) => e,
    }
}

/// A finished Rust build. Python's `_rust.RustBuildResult` wraps it and
/// materializes Python objects from these compact tables only on demand.
#[pyclass(frozen, module = "starlark_to_nbt._core")]
struct Build {
    node: stnbt_core::ir::Node,
    result: stnbt_core::pipeline::BuildResult,
    /// Distinct provenances, indexed in first-seen order.
    provenances: Vec<std::sync::Arc<stnbt_core::model::Provenance>>,
    provenance_index: std::collections::HashMap<usize, usize>,
}

fn prov_key(p: &std::sync::Arc<stnbt_core::model::Provenance>) -> usize {
    std::sync::Arc::as_ptr(p) as usize
}

impl Build {
    fn new(node: stnbt_core::ir::Node, result: stnbt_core::pipeline::BuildResult) -> Build {
        let mut provenances = Vec::new();
        let mut provenance_index = std::collections::HashMap::new();
        let all = result.operations.iter().map(|o| &o.provenance).chain(result.volume.entities.iter().map(|e| &e.provenance));
        for p in all {
            provenance_index.entry(prov_key(p)).or_insert_with(|| {
                provenances.push(p.clone());
                provenances.len() - 1
            });
        }
        Build { node, result, provenances, provenance_index }
    }

    fn prov(&self, p: &std::sync::Arc<stnbt_core::model::Provenance>) -> usize {
        self.provenance_index[&prov_key(p)]
    }
}

#[pymethods]
impl Build {
    /// `(min, max)` of the root box.
    fn bounds(&self) -> ([i32; 3], [i32; 3]) {
        let b = self.result.volume.bounds;
        (b.min.to_array(), b.max.to_array())
    }

    fn ground_level(&self) -> i32 {
        self.result.metadata.ground_level
    }

    fn voxel_count(&self) -> usize {
        self.result.volume.voxels.len()
    }

    /// Block table: `(block_type, block_state, block_nbt or None)` per id.
    fn blocks<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(py);
        for i in 0..self.result.blocks.len() {
            let b = self.result.blocks.get(stnbt_core::blocks::BlockId(i as u32));
            let state: Dict = b.block_state.iter().map(|(k, v)| (k.clone(), Val::Str(v.clone()))).collect();
            let nbt = b.block_nbt.clone().map_or(Val::Null, Val::Dict);
            out.append((b.block_type.as_str(), convert::from_val(py, &Val::Dict(state))?, convert::from_val(py, &nbt)?))?;
        }
        Ok(out)
    }

    /// Provenance table: `(component_path, (min, max), (file, line) or None)`.
    fn provenances<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(py);
        for p in &self.provenances {
            let r = p.assigned_region;
            let source = p.source.as_ref().map(|s| (s.file.as_str(), s.line));
            out.append((p.component_path.as_str(), (r.min.to_array(), r.max.to_array()), source))?;
        }
        Ok(out)
    }

    /// `(x, y, z, block_id, provenance_id, phase)` per voxel, in y/z/x order.
    fn voxels<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(py);
        for p in self.result.volume.sorted_points() {
            let v = &self.result.volume.voxels[&p];
            out.append((p.x, p.y, p.z, v.block.0, self.prov(&v.provenance), v.phase as u8))?;
        }
        Ok(out)
    }

    /// Block id at a cell; unwritten cells are air (id 0).
    fn block_at(&self, x: i32, y: i32, z: i32) -> u32 {
        self.result.volume.block_at(stnbt_core::model::Point::new(x, y, z)).0
    }

    /// `(pos, entity_type, nbt, yaw, pitch, provenance_id, sequence)` per entity.
    fn entities<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(py);
        for e in &self.result.volume.entities {
            let nbt = e.entity.nbt.clone().map_or(Val::Null, Val::Dict);
            out.append((e.pos.to_array(), e.entity.entity_type.as_str(), convert::from_val(py, &nbt)?, e.entity.yaw, e.entity.pitch, self.prov(&e.provenance), e.sequence))?;
        }
        Ok(out)
    }

    /// `(phase, kind, [(x, y, z, block_id)], provenance_id, assembly, sequence)` per operation.
    fn operations<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(py);
        for op in &self.result.operations {
            let writes: Vec<(i32, i32, i32, u32)> = op.writes.iter().map(|w| (w.pos.x, w.pos.y, w.pos.z, w.block.0)).collect();
            out.append((op.phase as u8, op.kind.as_str(), writes, self.prov(&op.provenance), op.assembly_name.as_deref(), op.sequence))?;
        }
        Ok(out)
    }

    fn write_structure_nbt(&self, py: Python<'_>, path: std::path::PathBuf) -> PyResult<()> {
        stnbt_core::serialize::write_structure_nbt(&self.result.volume, &self.result.blocks, &path).map_err(|e| core_error(py, &e))
    }

    #[pyo3(signature = (nbt_path, debug_dir=None))]
    fn write_outputs(&self, py: Python<'_>, nbt_path: std::path::PathBuf, debug_dir: Option<std::path::PathBuf>) -> PyResult<()> {
        stnbt_core::serialize::write_build_outputs(&self.node, &self.result, &nbt_path, debug_dir.as_deref()).map_err(|e| core_error(py, &e))
    }
}

/// Validate and build a raw tree with the Rust core. Raises
/// `CoreBuildError(diagnostics)` on failure.
#[pyfunction]
#[pyo3(signature = (tree, props, root_size=None, source_file=None))]
fn build<'py>(py: Python<'py>, tree: &Bound<'py, PyAny>, props: &Bound<'py, PyAny>, root_size: Option<[i32; 3]>, source_file: Option<&str>) -> PyResult<Build> {
    let value = convert::to_val(tree)?;
    let Val::Dict(props) = convert::to_val(props)? else {
        return Err(pyo3::exceptions::PyTypeError::new_err("props must be a dict"));
    };
    let node = stnbt_core::schema::parse_node(&value, source_file).map_err(|e| core_error(py, &e))?;
    let size = root_size.map(|[x, y, z]| stnbt_core::model::Point::new(x, y, z));
    let result = stnbt_core::pipeline::build(&node, &props, size).map_err(|e| core_error(py, &e))?;
    Ok(Build::new(node, result))
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(parse_ir, m)?)?;
    m.add_function(wrap_pyfunction!(lower_tree, m)?)?;
    m.add_function(wrap_pyfunction!(build_tree, m)?)?;
    m.add_function(wrap_pyfunction!(write_tree, m)?)?;
    m.add_function(wrap_pyfunction!(build, m)?)?;
    m.add_function(wrap_pyfunction!(build_fingerprint, m)?)?;
    m.add_class::<Build>()?;
    m.add("CoreBuildError", m.py().get_type::<CoreBuildError>())?;
    Ok(())
}
