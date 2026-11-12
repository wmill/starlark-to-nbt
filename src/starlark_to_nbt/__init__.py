"""Declarative Minecraft structures authored in Starlark."""

from .ir import BuildMetadata
from .pipeline import BuildResult, build_file, build_source, engine


def build_fingerprint() -> str:
    """Identifies everything outside `lib/` and the Python sources that can
    change build output: the active engine and the compiled Rust core (a hash
    of its sources and the prelude, baked in at build time). Output caches
    should key on it along with their own hash of `lib/` and `src/`."""
    from . import _core
    return f"{engine()}-{_core.version()}-{_core.build_fingerprint()}"


__all__ = ["BuildMetadata", "BuildResult", "build_file", "build_fingerprint", "build_source", "engine"]
