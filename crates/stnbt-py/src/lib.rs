//! Python bindings: the `starlark_to_nbt._core` extension module.
//!
//! Kept deliberately thin — conversion between Python values and core types
//! only. Pipeline logic belongs in `stnbt-core`.

use pyo3::prelude::*;

/// Version of the Rust core this extension was built from.
#[pyfunction]
fn version() -> &'static str {
    stnbt_core::version()
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}
