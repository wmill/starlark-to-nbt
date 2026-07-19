"""Declarative Minecraft structures authored in Starlark."""

from .ir import BuildMetadata
from .pipeline import BuildResult, build_file

__all__ = ["BuildMetadata", "BuildResult", "build_file"]
