"""Rust Starlark evaluation (crates/stnbt-core/src/eval) vs the Python
runtime (starlark-pyo3).

Both evaluate every corpus case with the same inputs, and the raw trees
must be identical as unsorted JSON, so key order and int/float matter.
"""
from __future__ import annotations

import json

import pytest

from _corpus import case_names, eval_inputs
from starlark_to_nbt import _core
from starlark_to_nbt.starlark_runtime import evaluate_source_raw

pytestmark = pytest.mark.parity


@pytest.mark.parametrize("name", case_names())
def test_corpus_evaluates_identically(name):
    inputs = eval_inputs(name)
    expected = evaluate_source_raw(inputs.source, inputs.filename, inputs.entry, inputs.props, **inputs.loader)
    actual = _core.evaluate_source(inputs.source, inputs.filename, inputs.entry, inputs.props, **inputs.loader)
    assert json.dumps(actual) == json.dumps(expected)
