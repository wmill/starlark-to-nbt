"""The native `starlark-to-nbt` binary (crates/stnbt-cli) against the golden
manifest and the Python CLI.

It covers every golden case the CLI can express: examples, church with
props, and every showcase component at all four rotations. Library cases
need the service's loader root and mounts, which the CLI doesn't take; the
pipeline covers those. Error text and exit codes must match `cli.py`.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _corpus import ROOT, SHOWCASE, showcase_names

pytestmark = pytest.mark.parity

MANIFEST = json.loads((ROOT / "tests" / "golden" / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def binary() -> Path:
    subprocess.run(["cargo", "build", "--release", "-q", "-p", "stnbt-cli"], cwd=ROOT, check=True)
    return ROOT / "target" / "release" / "starlark-to-nbt"


def _cli_cases() -> dict[str, list[str]]:
    cases = {f"example/{p.stem}": [str(p)] for p in sorted((ROOT / "examples").glob("*.star"))}
    cases["example/church@11x4x19"] = [str(ROOT / "examples" / "church.star"),
                                       "--arg", "width=11", "--arg", "length=19", "--arg", "height=4"]
    for name in showcase_names():
        cases[f"showcase/{name}"] = [str(SHOWCASE), "--arg", f"name={name}"]
        for rotation in (90, 180, 270):
            cases[f"showcase/{name}@{rotation}"] = [str(SHOWCASE), "--entry", "rotated", "--arg", f"name={name}",
                                                   "--arg", f"rotation={rotation}"]
    return cases


CLI_CASES = _cli_cases()


def test_every_cli_case_is_in_the_manifest():
    assert CLI_CASES.keys() <= MANIFEST["builds"].keys()


@pytest.mark.parametrize("name", sorted(CLI_CASES))
def test_native_cli_matches_golden(name, binary, tmp_path):
    output = tmp_path / "out.nbt"
    subprocess.run([binary, "build", *CLI_CASES[name], "--output", output], check=True)
    expected = MANIFEST["builds"][name]
    payload = gzip.decompress(output.read_bytes())
    assert hashlib.sha256(payload).hexdigest() == expected["nbt_sha256"]
    assert json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8")) == expected["meta"]


def _python_cli(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "STARLARK_TO_NBT_ENGINE": "python"}
    console_script = Path(sys.executable).parent / "starlark-to-nbt"
    return subprocess.run([console_script, *args], capture_output=True, text=True, env=env)


@pytest.mark.parametrize("source", [
    'def build():\n    return component("C", {}, group([place_block([0, 0, 0], block("minecraft:stone")),'
    ' place_block([0, 0, 0], block("minecraft:dirt"))]), min_size=[1, 1, 1])\n',
    'def build():\n    return component("C", {}, place_block([0, 1, 0], block("minecraft:redstone_wire")),'
    ' min_size=[1, 2, 1])\n',
    'def build():\n    return {"kind": "nope"}\n',
])
def test_build_errors_match_python_cli(source, binary, tmp_path):
    script = tmp_path / "bad.star"
    script.write_text(source, encoding="utf-8")
    native = subprocess.run([binary, "build", script, "--output", tmp_path / "n.nbt"], capture_output=True, text=True)
    python = _python_cli("build", str(script), "--output", str(tmp_path / "p.nbt"))
    assert native.returncode == python.returncode == 1
    assert native.stderr == python.stderr


def test_usage_errors_exit_2(binary, tmp_path):
    bad_arg = subprocess.run([binary, "build", "x.star", "--arg", "noequals", "--output", tmp_path / "o.nbt"],
                             capture_output=True, text=True)
    assert bad_arg.returncode == 2 and "expected NAME=VALUE" in bad_arg.stderr
    assert subprocess.run([binary, "build", "x.star"], capture_output=True).returncode == 2
