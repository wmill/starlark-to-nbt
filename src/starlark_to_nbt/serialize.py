"""Structure NBT output (written by the Rust core).

Output is sparse (only written voxels; carved cells stay explicit air),
deterministic (gzip mtime 0), and Minecraft 1.21.7 (`DATA_VERSION_1_21_7`).
"""
from __future__ import annotations

from pathlib import Path

DATA_VERSION_1_21_7 = 4438


def write_structure_nbt(volume, path: str | Path) -> None:
    """Write a build's `volume` (`BuildResult.volume`) as gzipped structure NBT."""
    volume._result.write_structure_nbt(path)


__all__ = ["DATA_VERSION_1_21_7", "write_structure_nbt"]
