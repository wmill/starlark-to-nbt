"""Declarative Minecraft structures authored in Starlark, built by a Rust core."""

from .ir import BuildMetadata
from .pipeline import BuildResult, build_file, build_source, evaluate_source


def build_fingerprint() -> str:
    """Identifies the compiled core (a hash of its Rust sources and Starlark
    prelude, baked in at build time). Output caches should key on it along
    with their own hash of `lib/` and `src/`."""
    from . import _core
    return f"rust-{_core.version()}-{_core.build_fingerprint()}"


__all__ = ["BuildMetadata", "BuildResult", "build_file", "build_fingerprint", "build_source", "evaluate_source"]
