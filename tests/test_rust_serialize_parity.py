"""Rust serialization (crates/stnbt-core/src/serialize.rs) vs Python's
`write_build_outputs`.

Every corpus case must write byte-identical decompressed structure NBT and
`.meta.json`. Gzip bytes are compared separately, because parity there also
depends on the zlib version each side links. For cases whose root box is
small enough to keep `dense.json` reasonable, all five debug-stage files
must match byte for byte too.
"""
from __future__ import annotations

import gzip

import pytest

from _corpus import case_names, load_case
from starlark_to_nbt import _core
from starlark_to_nbt.model import Point
from starlark_to_nbt.pipeline import _finish_build, _root_size, write_build_outputs
from starlark_to_nbt.schema import parse_node

pytestmark = pytest.mark.parity

DEBUG_FILES = ["component-ir.json", "resolved.json", "operations.json", "entities.json", "dense.json"]
DEBUG_MAX_VOLUME = 40_000


def _write_both(case, tmp_path, debug: bool):
    node = parse_node(case.tree, source_file=case.source_file)
    root = Point(*case.root_size) if case.root_size else _root_size(node, case.props)
    py_dir, rs_dir = tmp_path / "py", tmp_path / "rs"
    py_dir.mkdir()
    rs_dir.mkdir()
    write_build_outputs(_finish_build(node, case.props, root), py_dir / "out.nbt",
                        py_dir / "debug" if debug else None)
    error = _core.write_tree(case.tree, root.to_list(), case.source_file, rs_dir / "out.nbt",
                             rs_dir / "debug" if debug else None)
    assert error is None, error
    return py_dir, rs_dir


@pytest.mark.parametrize("name", case_names())
def test_corpus_writes_identical_nbt_and_meta(name, tmp_path):
    case = load_case(name)
    py_dir, rs_dir = _write_both(case, tmp_path, debug=False)
    py_gz, rs_gz = (py_dir / "out.nbt").read_bytes(), (rs_dir / "out.nbt").read_bytes()
    assert gzip.decompress(rs_gz) == gzip.decompress(py_gz)
    assert (rs_dir / "out.meta.json").read_bytes() == (py_dir / "out.meta.json").read_bytes()
    assert rs_gz == py_gz, "decompressed NBT matches but gzip bytes differ"


def _small_cases() -> list[str]:
    names = []
    for name in case_names():
        if name.startswith("showcase/") and "@" in name:
            continue  # rotations add nothing new for debug dumps
        names.append(name)
    return names


@pytest.mark.parametrize("name", _small_cases())
def test_debug_dumps_are_byte_identical(name, tmp_path):
    case = load_case(name)
    node = parse_node(case.tree, source_file=case.source_file)
    root = Point(*case.root_size) if case.root_size else _root_size(node, case.props)
    if root.x * root.y * root.z > DEBUG_MAX_VOLUME:
        pytest.skip(f"root volume {root.x * root.y * root.z} makes dense.json too large to compare quickly")
    py_dir, rs_dir = _write_both(case, tmp_path, debug=True)
    for filename in DEBUG_FILES:
        assert (rs_dir / "debug" / filename).read_bytes() == (py_dir / "debug" / filename).read_bytes(), filename
