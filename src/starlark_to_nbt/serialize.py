from __future__ import annotations

import json
import gzip
from pathlib import Path
from typing import Any

import nbtlib
from nbtlib import Byte, Compound, Double, File, Int, List, String

from .execute import SparseVolume, dense_to_dict
from .model import BlockSpec, Point


DATA_VERSION_1_21_7 = 4438


def write_json(value: Any, path: str | Path) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_structure_nbt(volume: SparseVolume, path: str | Path) -> None:
    # Only written voxels are emitted; untouched cells are absent from the
    # template, so pasting the structure leaves the existing terrain there.
    # Carved cells were written as explicit air and still clear their cell.
    written = _written(volume)
    specs = {block.key(): block for _, block in written}
    ordered_specs = sorted(specs.values(), key=lambda block: (block.block_type != "minecraft:air", block.key()))
    palette_index = {block.key(): index for index, block in enumerate(ordered_specs)}

    palette = List[Compound]([_palette_entry(block) for block in ordered_specs])
    blocks = List[Compound]()
    origin = volume.bounds.min
    for point, block in written:
        relative = point - origin
        entry = Compound({
            "state": Int(palette_index[block.key()]),
            "pos": List[Int]([Int(relative.x), Int(relative.y), Int(relative.z)]),
        })
        if block.block_nbt:
            # Block-entity data rides on the block instance, never the palette.
            entry["nbt"] = _to_nbt(block.block_nbt)
        blocks.append(entry)

    root = Compound({
        "DataVersion": Int(DATA_VERSION_1_21_7),
        "size": List[Int]([Int(v) for v in volume.bounds.size.to_list()]),
        "palette": palette,
        "blocks": blocks,
        "entities": List[Compound](),
    })
    # Avoid gzip's current-time header so identical builds are byte-for-byte stable.
    with Path(path).open("wb") as raw_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as gzipped_file:
            File(root).write(gzipped_file)


def _written(volume: SparseVolume) -> list[tuple[Point, BlockSpec]]:
    return [
        (point, volume.voxels[point].block)
        for point in sorted(volume.voxels, key=lambda p: (p.y, p.z, p.x))
    ]


def _to_nbt(value: Any) -> Any:
    if isinstance(value, bool):  # before int: bool is an int subclass
        return Byte(1 if value else 0)
    if isinstance(value, int):
        return Int(value)
    if isinstance(value, float):
        return Double(value)
    if isinstance(value, str):
        return String(value)
    if isinstance(value, dict):
        return Compound({key: _to_nbt(item) for key, item in value.items()})
    if isinstance(value, list):
        tags = [_to_nbt(item) for item in value]
        if not tags:
            return List[String]([])
        return List[type(tags[0])](tags)
    raise ValueError(f"cannot serialize {type(value).__name__} as NBT")


def _palette_entry(block: BlockSpec) -> Compound:
    value = Compound({"Name": String(block.block_type)})
    if block.block_state:
        value["Properties"] = Compound({key: String(state) for key, state in sorted(block.block_state.items())})
    return value


__all__ = ["DATA_VERSION_1_21_7", "dense_to_dict", "write_json", "write_structure_nbt"]
