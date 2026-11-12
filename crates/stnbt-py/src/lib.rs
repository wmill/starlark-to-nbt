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

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(parse_ir, m)?)?;
    m.add_function(wrap_pyfunction!(lower_tree, m)?)?;
    Ok(())
}
