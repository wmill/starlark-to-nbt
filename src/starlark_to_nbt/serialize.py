from __future__ import annotations

import json
import gzip
from pathlib import Path
from typing import Any

import nbtlib
from nbtlib import Compound, File, Int, List, String

from .execute import SparseVolume, dense_to_dict
from .model import BlockSpec, Point


DATA_VERSION_1_21_7 = 4438


def write_json(value: Any, path: str | Path) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_structure_nbt(volume: SparseVolume, path: str | Path) -> None:
    specs = {volume.block_at(point).key(): volume.block_at(point) for point in _points(volume)}
    ordered_specs = sorted(specs.values(), key=lambda block: (block.block_type != "minecraft:air", block.key()))
    palette_index = {block.key(): index for index, block in enumerate(ordered_specs)}

    palette = List[Compound]([_palette_entry(block) for block in ordered_specs])
    blocks = List[Compound]()
    origin = volume.bounds.min
    for point in _points(volume):
        relative = point - origin
        block = volume.block_at(point)
        blocks.append(Compound({
            "state": Int(palette_index[block.key()]),
            "pos": List[Int]([Int(relative.x), Int(relative.y), Int(relative.z)]),
        }))

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


def _points(volume: SparseVolume):
    bounds = volume.bounds
    for y in range(bounds.min.y, bounds.max.y):
        for z in range(bounds.min.z, bounds.max.z):
            for x in range(bounds.min.x, bounds.max.x):
                yield Point(x, y, z)


def _palette_entry(block: BlockSpec) -> Compound:
    value = Compound({"Name": String(block.block_type)})
    if block.block_state:
        value["Properties"] = Compound({key: String(state) for key, state in sorted(block.block_state.items())})
    return value


__all__ = ["DATA_VERSION_1_21_7", "dense_to_dict", "write_json", "write_structure_nbt"]
