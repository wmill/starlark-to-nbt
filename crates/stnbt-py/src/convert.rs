//! Python <-> `Val` conversion, in one recursive pass each way.
//!
//! Python input comes from starlark-pyo3, which marshals through JSON, so it
//! is already JSON-shaped: str keys, no tuples, ints that fit in i64.
//! Anything else is rejected with a TypeError/OverflowError rather than
//! guessed at.

use pyo3::exceptions::{PyOverflowError, PyTypeError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString, PyTuple};

use stnbt_core::val::{Dict, Val};

pub fn to_val(obj: &Bound<'_, PyAny>) -> PyResult<Val> {
    if obj.is_none() {
        return Ok(Val::Null);
    }
    // bool before int: Python's bool is an int subclass.
    if let Ok(b) = obj.cast::<PyBool>() {
        return Ok(Val::Bool(b.is_true()));
    }
    if obj.is_instance_of::<PyInt>() {
        return obj
            .extract::<i64>()
            .map(Val::Int)
            .map_err(|_| PyOverflowError::new_err("integer does not fit in 64 bits"));
    }
    if let Ok(f) = obj.cast::<PyFloat>() {
        return Ok(Val::Float(f.value()));
    }
    if let Ok(s) = obj.cast::<PyString>() {
        return Ok(Val::Str(s.to_str()?.to_owned()));
    }
    if let Ok(list) = obj.cast::<PyList>() {
        return list.iter().map(|item| to_val(&item)).collect::<PyResult<_>>().map(Val::List);
    }
    if let Ok(tuple) = obj.cast::<PyTuple>() {
        return tuple.iter().map(|item| to_val(&item)).collect::<PyResult<_>>().map(Val::List);
    }
    if let Ok(dict) = obj.cast::<PyDict>() {
        let mut out = Dict::with_capacity(dict.len());
        for (key, value) in dict.iter() {
            let key = key
                .cast::<PyString>()
                .map_err(|_| PyTypeError::new_err("object keys must be strings"))?
                .to_str()?
                .to_owned();
            out.insert(key, to_val(&value)?);
        }
        return Ok(Val::Dict(out));
    }
    Err(PyTypeError::new_err(format!(
        "cannot convert {} to a JSON-compatible value",
        obj.get_type().name()?
    )))
}

pub fn from_val<'py>(py: Python<'py>, value: &Val) -> PyResult<Bound<'py, PyAny>> {
    Ok(match value {
        Val::Null => py.None().into_bound(py),
        Val::Bool(b) => PyBool::new(py, *b).to_owned().into_any(),
        Val::Int(i) => i.into_pyobject(py)?.into_any(),
        Val::Float(f) => PyFloat::new(py, *f).into_any(),
        Val::Str(s) => PyString::new(py, s).into_any(),
        Val::List(items) => {
            let list = PyList::empty(py);
            for item in items {
                list.append(from_val(py, item)?)?;
            }
            list.into_any()
        }
        Val::Dict(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, from_val(py, v)?)?;
            }
            dict.into_any()
        }
    })
}
