//! Python bindings: the `starlark_to_nbt._core` extension module.
//!
//! Kept deliberately thin — conversion between Python values and core types
//! only. Pipeline logic belongs in `stnbt-core`.

mod convert;

use pyo3::prelude::*;
use pyo3::types::PyList;

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

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(parse_ir, m)?)?;
    Ok(())
}
