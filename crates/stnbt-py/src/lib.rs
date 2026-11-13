//! Python bindings: the `starlark_to_nbt._core` extension module.
//!
//! Kept deliberately thin: argument conversion and result tables only. The
//! pipeline lives in `stnbt-core`, and `starlark_to_nbt.pipeline` wraps
//! these entry points in the public Python API.

mod convert;

use std::collections::{BTreeMap, HashMap};
use std::path::PathBuf;
use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyList;
use stnbt_core::blocks::BlockId;
use stnbt_core::ir::Node;
use stnbt_core::model::{BuildError, Point, Provenance};
use stnbt_core::pipeline::BuildResult;
use stnbt_core::val::{Dict, Val};

pyo3::create_exception!(
    _core,
    CoreBuildError,
    pyo3::exceptions::PyException,
    "A build failed; args[0] is the list of diagnostic dicts."
);

/// Version of the Rust core this extension was built from.
#[pyfunction]
fn version() -> &'static str {
    stnbt_core::version()
}

/// Fingerprint of the Rust sources (prelude included) this extension was
/// built from (see build.rs). Output caches must include it.
#[pyfunction]
fn build_fingerprint() -> &'static str {
    env!("STNBT_BUILD_FINGERPRINT")
}

/// Diagnostics as dicts with every field.
fn diagnostics_val(err: &BuildError) -> Val {
    Val::List(
        err.diagnostics
            .iter()
            .map(|d| {
                let mut m = Dict::new();
                m.insert("code".into(), Val::Str(d.code.into()));
                m.insert("component_path".into(), Val::Str(d.component_path.clone()));
                m.insert("message".into(), Val::Str(d.message.clone()));
                m.insert("region".into(), d.region.as_ref().map_or(Val::Null, |r| r.to_val()));
                m.insert("coordinates".into(), d.coordinates.map_or(Val::Null, |p| p.to_val()));
                m.insert("details".into(), Val::Dict(d.details.clone()));
                m.insert(
                    "source".into(),
                    d.source.as_ref().map_or(Val::Null, |s| {
                        Val::List(vec![Val::Str(s.file.clone()), s.line.map_or(Val::Null, |l| Val::Int(l.into()))])
                    }),
                );
                Val::Dict(m)
            })
            .collect(),
    )
}

fn core_error(py: Python<'_>, err: &BuildError) -> PyErr {
    match convert::from_val(py, &diagnostics_val(err)) {
        Ok(diags) => CoreBuildError::new_err((diags.unbind(),)),
        Err(e) => e,
    }
}

fn load_options(
    base_dir: Option<PathBuf>,
    loader_root: Option<PathBuf>,
    mounts: Option<BTreeMap<String, PathBuf>>,
) -> stnbt_core::eval::LoadOptions {
    stnbt_core::eval::LoadOptions { base_dir, loader_root, mounts: mounts.unwrap_or_default().into_iter().collect() }
}

fn props_dict(props: &Bound<'_, PyAny>) -> PyResult<Dict> {
    match convert::to_val(props)? {
        Val::Dict(d) => Ok(d),
        _ => Err(pyo3::exceptions::PyTypeError::new_err("props must be a dict")),
    }
}

/// A finished build. `starlark_to_nbt.pipeline.BuildResult` wraps it and
/// materializes Python objects from these compact tables only on demand.
#[pyclass(frozen, module = "starlark_to_nbt._core")]
struct Build {
    node: Node,
    result: BuildResult,
    /// Distinct provenances, indexed in first-seen order.
    provenances: Vec<Arc<Provenance>>,
    provenance_index: HashMap<usize, usize>,
}

fn prov_key(p: &Arc<Provenance>) -> usize {
    Arc::as_ptr(p) as usize
}

impl Build {
    fn new(node: Node, result: BuildResult) -> Build {
        let mut provenances = Vec::new();
        let mut provenance_index = HashMap::new();
        let all = result.operations.iter().map(|o| &o.provenance).chain(result.volume.entities.iter().map(|e| &e.provenance));
        for p in all {
            provenance_index.entry(prov_key(p)).or_insert_with(|| {
                provenances.push(p.clone());
                provenances.len() - 1
            });
        }
        Build { node, result, provenances, provenance_index }
    }

    fn prov(&self, p: &Arc<Provenance>) -> usize {
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

    /// The script's `stage_delay_ticks` metadata, or `None`.
    fn stage_delay_ticks(&self) -> Option<i32> {
        self.result.metadata.stage_delay_ticks
    }

    /// `(stage, block_count)` per install stage, in order; empty unless the
    /// build uses more than one stage.
    fn stages(&self) -> Vec<(u8, usize)> {
        self.result.stages.iter().map(|l| (l.stage, l.volume.voxels.len())).collect()
    }

    /// Write one install stage's cells as structure NBT (root-box size).
    fn write_stage_nbt(&self, py: Python<'_>, stage: u8, path: PathBuf) -> PyResult<()> {
        let Some(layer) = self.result.stages.iter().find(|l| l.stage == stage) else {
            return Err(pyo3::exceptions::PyValueError::new_err(format!("build has no install stage {stage}")));
        };
        stnbt_core::serialize::write_structure_nbt(&layer.volume, &self.result.blocks, &path).map_err(|e| core_error(py, &e))
    }

    /// The root component's props, or `None` if the root isn't a component.
    fn root_props<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        match &self.node {
            Node::Component(c) => convert::from_val(py, &Val::Dict(c.props.clone())),
            _ => Ok(py.None().into_bound(py)),
        }
    }

    /// Block table: `(block_type, block_state, block_nbt or None)` per id.
    fn blocks<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(py);
        for i in 0..self.result.blocks.len() {
            let b = self.result.blocks.get(BlockId(i as u32));
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
        self.result.volume.block_at(Point::new(x, y, z)).0
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

    fn write_structure_nbt(&self, py: Python<'_>, path: PathBuf) -> PyResult<()> {
        stnbt_core::serialize::write_structure_nbt(&self.result.volume, &self.result.blocks, &path).map_err(|e| core_error(py, &e))
    }

    #[pyo3(signature = (nbt_path, debug_dir=None))]
    fn write_outputs(&self, py: Python<'_>, nbt_path: PathBuf, debug_dir: Option<PathBuf>) -> PyResult<()> {
        stnbt_core::serialize::write_build_outputs(&self.node, &self.result, &nbt_path, debug_dir.as_deref()).map_err(|e| core_error(py, &e))
    }
}

/// Evaluate a script and return its raw tagged-dict tree, unvalidated.
#[pyfunction]
#[pyo3(signature = (source, filename, entry, props, base_dir=None, loader_root=None, mounts=None))]
#[allow(clippy::too_many_arguments)]
fn evaluate_source<'py>(
    py: Python<'py>, source: &str, filename: &str, entry: &str, props: &Bound<'py, PyAny>,
    base_dir: Option<PathBuf>, loader_root: Option<PathBuf>, mounts: Option<BTreeMap<String, PathBuf>>,
) -> PyResult<Bound<'py, PyAny>> {
    let props = props_dict(props)?;
    let opts = load_options(base_dir, loader_root, mounts);
    let tree = py.detach(|| stnbt_core::eval::evaluate_source(source, filename, entry, &props, &opts));
    convert::from_val(py, &tree.map_err(|e| core_error(py, &e))?)
}

/// Evaluate, validate, and build. Raises `CoreBuildError(diagnostics)`.
#[pyfunction]
#[pyo3(signature = (source, filename, entry, props, root_size=None, base_dir=None, loader_root=None, mounts=None))]
#[allow(clippy::too_many_arguments)]
fn build_source(
    py: Python<'_>, source: &str, filename: &str, entry: &str, props: &Bound<'_, PyAny>,
    root_size: Option<[i32; 3]>, base_dir: Option<PathBuf>, loader_root: Option<PathBuf>,
    mounts: Option<BTreeMap<String, PathBuf>>,
) -> PyResult<Build> {
    let props = props_dict(props)?;
    let opts = load_options(base_dir, loader_root, mounts);
    let size = root_size.map(|[x, y, z]| Point::new(x, y, z));
    let built = py.detach(|| -> Result<_, BuildError> {
        let tree = stnbt_core::eval::evaluate_source(source, filename, entry, &props, &opts)?;
        let node = stnbt_core::schema::parse_node(&tree, Some(filename))?;
        let result = stnbt_core::pipeline::build(&node, &props, size)?;
        Ok((node, result))
    });
    let (node, result) = built.map_err(|e| core_error(py, &e))?;
    Ok(Build::new(node, result))
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(build_fingerprint, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_source, m)?)?;
    m.add_function(wrap_pyfunction!(build_source, m)?)?;
    m.add_class::<Build>()?;
    m.add("CoreBuildError", m.py().get_type::<CoreBuildError>())?;
    Ok(())
}
