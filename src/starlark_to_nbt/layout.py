from __future__ import annotations

from .ir import Component, Fill, Group, Inset, Node, Repeat, ResolvedNode, Split, TransformNode
from .model import Axis, Box, BuildError, Diagnostic, Point, Transform


def _diagnostic(code: str, message: str, path: str, region: Box) -> BuildError:
    return BuildError(Diagnostic(code, message, path, region=region))


def _component_path(node: Node, parent: str, label: str | None = None) -> str:
    if isinstance(node, Component):
        if label and label.startswith("item["):
            segment = f"{node.name}{label.removeprefix('item')}"
        elif label and label.startswith("child["):
            segment = f"{label}/{node.name}"
        else:
            segment = node.name
    else:
        segment = label or type(node).__name__
    return f"{parent}/{segment}" if parent else segment


def resolve(root: Node, root_box: Box) -> ResolvedNode:
    return _resolve(root, root_box, "", ())


def _resolve(node: Node, region: Box, parent_path: str, transforms: tuple[Transform, ...], label: str | None = None) -> ResolvedNode:
    path = _component_path(node, parent_path, label)

    if isinstance(node, Component):
        if node.min_size:
            actual = region.size
            if any(a < required for a, required in zip(actual.to_list(), node.min_size.to_list())):
                raise _diagnostic("component_too_small", f"requires at least {node.min_size.to_list()}, assigned {actual.to_list()}", path, region)
        child = _resolve(node.body, region, path, transforms, "body")
        return ResolvedNode(node, region, path, transforms, (child,))

    if isinstance(node, Group):
        children = tuple(_resolve(child, region, path, transforms, f"child[{i}]") for i, child in enumerate(node.children))
        return ResolvedNode(node, region, path, transforms, children)

    if isinstance(node, Inset):
        mins = region.min
        maxs = region.max
        for axis in Axis:
            low, high = node.amounts[axis]
            mins = mins.replace(axis, mins.component(axis) + low)
            maxs = maxs.replace(axis, maxs.component(axis) - high)
        try:
            inner = Box(mins, maxs)
        except ValueError as exc:
            raise _diagnostic("inset_collapsed", f"insets collapse assigned region: {exc}", path, region) from exc
        child = _resolve(node.child, inner, path, transforms, "child")
        return ResolvedNode(node, region, path, transforms, (child,))

    if isinstance(node, Split):
        available = region.extent(node.axis)
        fixed_total = sum(size.value for size in node.sizes if hasattr(size, "value"))
        fill_count = sum(isinstance(size, Fill) for size in node.sizes)
        remaining = available - fixed_total
        if remaining < 0:
            raise _diagnostic("split_overflow", f"fixed sizes require {fixed_total}, but only {available} is available", path, region)
        if fill_count == 0 and remaining != 0:
            raise _diagnostic("split_underflow", f"fixed sizes cover {fixed_total}, but assigned extent is {available}", path, region)
        base, remainder = divmod(remaining, fill_count) if fill_count else (0, 0)
        if fill_count and base == 0:
            raise _diagnostic("split_empty_fill", "one or more fill allocations would be empty", path, region)
        cursor = region.min.component(node.axis)
        fill_index = 0
        children = []
        for i, (size, child_node) in enumerate(zip(node.sizes, node.children)):
            if isinstance(size, Fill):
                extent = base + (1 if fill_index < remainder else 0)
                fill_index += 1
            else:
                extent = size.value
            child_min = region.min.replace(node.axis, cursor)
            cursor += extent
            child_max = region.max.replace(node.axis, cursor)
            children.append(_resolve(child_node, Box(child_min, child_max), path, transforms, f"child[{i}]"))
        return ResolvedNode(node, region, path, transforms, tuple(children))

    if isinstance(node, Repeat):
        required = node.count * node.child_extent + (node.count - 1) * node.gap
        available = region.extent(node.axis)
        if required > available:
            raise _diagnostic("repeat_overflow", f"repeat requires {required} blocks, but only {available} are available", path, region)
        children = []
        cursor = region.min.component(node.axis)
        for i in range(node.count):
            child_min = region.min.replace(node.axis, cursor)
            child_max = region.max.replace(node.axis, cursor + node.child_extent)
            children.append(_resolve(node.child, Box(child_min, child_max), path, transforms, f"item[{i}]"))
            cursor += node.child_extent + node.gap
        return ResolvedNode(node, region, path, transforms, tuple(children))

    if isinstance(node, TransformNode):
        transform = Transform(node.translation, node.rotation_y, node.child_size)
        footprint = Box.from_size(transform.footprint_size or node.child_size, region.min + node.translation)
        if not region.contains_box(footprint):
            raise _diagnostic("transform_overflow", f"transformed footprint {footprint.to_dict()} is outside assigned region", path, region)
        child_region = Box.from_size(node.child_size)
        child = _resolve(node.child, child_region, path, transforms + (Transform(region.min + node.translation, node.rotation_y, node.child_size),), "child")
        return ResolvedNode(node, region, path, transforms, (child,))

    return ResolvedNode(node, region, path, transforms)


def resolved_to_dict(node: ResolvedNode) -> dict:
    return {
        "kind": type(node.node).__name__,
        "path": node.path,
        "region": node.region.to_dict(),
        "children": [resolved_to_dict(child) for child in node.children],
    }
