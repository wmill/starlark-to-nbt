//! Region assignment (port of `layout.py`).
//!
//! `resolve` gives every node a half-open region and a component path.
//! Combinators fail loudly on overflow or underflow; geometry is never
//! clamped. Each node's `world_transforms` is an `Arc` shared by every node
//! under the same transform, so lowering can key its rotation cache on the
//! pointer.

use std::sync::Arc;

use crate::ir::{Node, SizeExpr};
use crate::model::{Axis, BuildError, Diagnostic, Point, Region, Transform};
use crate::val::Val;

#[derive(Debug)]
pub struct ResolvedNode<'a> {
    pub node: &'a Node,
    pub region: Region,
    pub path: String,
    pub world_transforms: Arc<[Transform]>,
    pub children: Vec<ResolvedNode<'a>>,
}

impl ResolvedNode<'_> {
    /// Python `layout.resolved_to_dict` (the `resolved.json` debug stage).
    pub fn to_val(&self) -> Val {
        let mut d = crate::val::Dict::with_capacity(4);
        d.insert("kind".into(), Val::Str(self.node.class_name().into()));
        d.insert("path".into(), Val::Str(self.path.clone()));
        d.insert("region".into(), self.region.to_val());
        d.insert("children".into(), Val::List(self.children.iter().map(ResolvedNode::to_val).collect()));
        Val::Dict(d)
    }
}

type R<T> = Result<T, BuildError>;

fn error(code: &'static str, message: String, path: &str, region: Region) -> BuildError {
    Diagnostic::new(code, message, path).with_region(region).into()
}

/// The label a parent gives a child: `body`, `child`, `child[i]`, or `item[i]`.
#[derive(Clone, Copy)]
enum Label {
    None,
    Body,
    Child,
    ChildIndex(usize),
    Item(usize),
}

fn component_path(node: &Node, parent: &str, label: Label) -> String {
    let segment = match (node, label) {
        (Node::Component(c), Label::Item(i)) => format!("{}[{i}]", c.name),
        (Node::Component(c), Label::ChildIndex(i)) => format!("child[{i}]/{}", c.name),
        (Node::Component(c), _) => c.name.clone(),
        (_, Label::None) => node.class_name().to_owned(),
        (_, Label::Body) => "body".to_owned(),
        (_, Label::Child) => "child".to_owned(),
        (_, Label::ChildIndex(i)) => format!("child[{i}]"),
        (_, Label::Item(i)) => format!("item[{i}]"),
    };
    if parent.is_empty() {
        segment
    } else {
        format!("{parent}/{segment}")
    }
}

pub fn resolve(root: &Node, root_region: Region) -> R<ResolvedNode<'_>> {
    resolve_node(root, root_region, "", &Arc::from(Vec::new()), Label::None)
}

fn resolve_node<'a>(
    node: &'a Node,
    region: Region,
    parent: &str,
    transforms: &Arc<[Transform]>,
    label: Label,
) -> R<ResolvedNode<'a>> {
    let path = component_path(node, parent, label);
    let leaf = |path: String, children: Vec<ResolvedNode<'a>>| ResolvedNode {
        node,
        region,
        path,
        world_transforms: transforms.clone(),
        children,
    };

    match node {
        Node::Component(c) => {
            if let Some(min) = c.min_size {
                let actual = region.size();
                if actual.x < min.x || actual.y < min.y || actual.z < min.z {
                    return Err(error(
                        "component_too_small",
                        format!("requires at least {}, assigned {}", min.list_str(), actual.list_str()),
                        &path,
                        region,
                    ));
                }
            }
            let child = resolve_node(&c.body, region, &path, transforms, Label::Body)?;
            Ok(leaf(path, vec![child]))
        }
        Node::Group { children } => {
            let kids = children
                .iter()
                .enumerate()
                .map(|(i, child)| resolve_node(child, region, &path, transforms, Label::ChildIndex(i)))
                .collect::<R<Vec<_>>>()?;
            Ok(leaf(path, kids))
        }
        Node::Inset { amounts, child } => {
            let (mut min, mut max) = (region.min, region.max);
            for axis in Axis::ALL {
                let (low, high) = amounts[axis.index()];
                min = min.with(axis, min.get(axis) + low);
                max = max.with(axis, max.get(axis) - high);
            }
            let inner = Region::new(min, max).map_err(|e| {
                error("inset_collapsed", format!("insets collapse assigned region: {e}"), &path, region)
            })?;
            let child = resolve_node(child, inner, &path, transforms, Label::Child)?;
            Ok(leaf(path, vec![child]))
        }
        Node::Split { axis, sizes, children } => {
            let axis = *axis;
            let available = i64::from(region.extent(axis));
            let fixed_total: i64 = sizes.iter().map(|s| match s { SizeExpr::Fixed(v) => i64::from(*v), SizeExpr::Fill => 0 }).sum();
            let fill_count = sizes.iter().filter(|s| matches!(s, SizeExpr::Fill)).count() as i64;
            let remaining = available - fixed_total;
            if remaining < 0 {
                return Err(error(
                    "split_overflow",
                    format!("fixed sizes require {fixed_total}, but only {available} is available"),
                    &path,
                    region,
                ));
            }
            if fill_count == 0 && remaining != 0 {
                return Err(error(
                    "split_underflow",
                    format!("fixed sizes cover {fixed_total}, but assigned extent is {available}"),
                    &path,
                    region,
                ));
            }
            let (base, remainder) = if fill_count > 0 { (remaining / fill_count, remaining % fill_count) } else { (0, 0) };
            if fill_count > 0 && base == 0 {
                return Err(error("split_empty_fill", "one or more fill allocations would be empty".into(), &path, region));
            }
            let mut cursor = region.min.get(axis);
            let mut fill_index = 0;
            let mut kids = Vec::with_capacity(children.len());
            for (i, (size, child)) in sizes.iter().zip(children).enumerate() {
                let extent = match size {
                    SizeExpr::Fill => {
                        let extent = base + i64::from(fill_index < remainder);
                        fill_index += 1;
                        extent as i32
                    }
                    SizeExpr::Fixed(v) => *v,
                };
                let child_min = region.min.with(axis, cursor);
                cursor += extent;
                let child_max = region.max.with(axis, cursor);
                let child_region = Region { min: child_min, max: child_max };
                kids.push(resolve_node(child, child_region, &path, transforms, Label::ChildIndex(i))?);
            }
            Ok(leaf(path, kids))
        }
        Node::Repeat { axis, count, child_extent, gap, child } => {
            let axis = *axis;
            let (count, extent, gap) = (i64::from(*count), i64::from(*child_extent), i64::from(*gap));
            let required = count * extent + (count - 1) * gap;
            let available = i64::from(region.extent(axis));
            if required > available {
                return Err(error(
                    "repeat_overflow",
                    format!("repeat requires {required} blocks, but only {available} are available"),
                    &path,
                    region,
                ));
            }
            let mut kids = Vec::with_capacity(count as usize);
            let mut cursor = region.min.get(axis);
            for i in 0..count as usize {
                let child_region = Region {
                    min: region.min.with(axis, cursor),
                    max: region.max.with(axis, cursor + extent as i32),
                };
                kids.push(resolve_node(child, child_region, &path, transforms, Label::Item(i))?);
                cursor += (extent + gap) as i32;
            }
            Ok(leaf(path, kids))
        }
        Node::Transform { translation, rotation, child_size, child } => {
            let origin = region.min + *translation;
            let placed = Transform { translation: origin, rotation: *rotation, source_size: *child_size };
            let footprint = Region { min: origin, max: origin + placed.footprint_size() };
            if !region.contains_box(&footprint) {
                return Err(error(
                    "transform_overflow",
                    format!("transformed footprint {} is outside assigned region", footprint.dict_str()),
                    &path,
                    region,
                ));
            }
            let child_region = Region { min: Point::ZERO, max: *child_size };
            let mut stack = transforms.to_vec();
            stack.push(placed);
            let child = resolve_node(child, child_region, &path, &Arc::from(stack), Label::Child)?;
            Ok(leaf(path, vec![child]))
        }
        Node::PlaceBlock { .. }
        | Node::PlaceEntity { .. }
        | Node::FillRegion { .. }
        | Node::CarveRegion { .. }
        | Node::PlaceAssembly { .. } => Ok(leaf(path, Vec::new())),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::Component;
    use crate::model::Rotation;

    fn leaf() -> Node {
        Node::Group { children: vec![] }
    }

    fn size(x: i32, y: i32, z: i32) -> Region {
        Region::from_size(Point::new(x, y, z), Point::ZERO).unwrap()
    }

    fn code(r: R<ResolvedNode<'_>>) -> &'static str {
        r.unwrap_err().diagnostics[0].code
    }

    // Ported from tests/test_schema_layout.py.
    #[test]
    fn split_allocates_fixed_and_fill_with_deterministic_remainder() {
        let node = Node::Split { axis: Axis::X, sizes: vec![SizeExpr::Fill, SizeExpr::Fixed(2), SizeExpr::Fill], children: vec![leaf(), leaf(), leaf()] };
        let r = resolve(&node, size(9, 1, 1)).unwrap();
        assert_eq!(r.children.iter().map(|c| c.region.extent(Axis::X)).collect::<Vec<_>>(), [4, 2, 3]);
        assert_eq!(r.children.iter().map(|c| c.region.min.x).collect::<Vec<_>>(), [0, 4, 6]);
        assert_eq!(r.children[2].region.max.x, 9);
    }

    #[test]
    fn split_and_repeat_report_insufficient_space() {
        let split = Node::Split { axis: Axis::X, sizes: vec![SizeExpr::Fixed(3), SizeExpr::Fixed(3)], children: vec![leaf(), leaf()] };
        assert_eq!(code(resolve(&split, size(5, 1, 1))), "split_overflow");
        assert_eq!(code(resolve(&split, size(7, 1, 1))), "split_underflow");
        let fills = Node::Split { axis: Axis::X, sizes: vec![SizeExpr::Fill, SizeExpr::Fill], children: vec![leaf(), leaf()] };
        assert_eq!(code(resolve(&fills, size(1, 1, 1))), "split_empty_fill");
        let repeat = Node::Repeat { axis: Axis::Z, count: 3, child_extent: 2, gap: 1, child: Box::new(leaf()) };
        let e = resolve(&repeat, size(1, 1, 7)).unwrap_err();
        assert_eq!(e.diagnostics[0].message, "repeat requires 8 blocks, but only 7 are available");
    }

    #[test]
    fn explicit_repeat_allocates_gaps_and_paths() {
        let node = Node::Repeat { axis: Axis::Z, count: 3, child_extent: 1, gap: 2, child: Box::new(leaf()) };
        let r = resolve(&node, size(2, 1, 8)).unwrap();
        assert_eq!(r.children.iter().map(|c| (c.region.min.z, c.region.max.z)).collect::<Vec<_>>(), [(0, 1), (3, 4), (6, 7)]);
        assert_eq!(r.children.iter().map(|c| c.path.as_str()).collect::<Vec<_>>(), ["Repeat/item[0]", "Repeat/item[1]", "Repeat/item[2]"]);
    }

    #[test]
    fn inset_allocates_inner_box_and_rejects_collapse() {
        let node = Node::Inset { amounts: [(1, 2), (1, 0), (2, 1)], child: Box::new(leaf()) };
        let r = resolve(&node, size(8, 3, 9)).unwrap();
        assert_eq!(r.children[0].region, Region::new(Point::new(1, 1, 2), Point::new(6, 3, 8)).unwrap());
        let collapsed = Node::Inset { amounts: [(1, 1), (0, 0), (0, 0)], child: Box::new(leaf()) };
        let e = resolve(&collapsed, size(2, 1, 1)).unwrap_err();
        assert_eq!(e.diagnostics[0].message,
            "insets collapse assigned region: box must have positive extents: Box(min=Point(x=1, y=0, z=0), max=Point(x=1, y=1, z=1))");
    }

    fn component(name: &str, body: Node, min_size: Option<Point>) -> Node {
        Node::Component(Box::new(Component { name: name.into(), props: Default::default(), body, min_size, source: None, metadata: None, validators: vec![] }))
    }

    #[test]
    fn component_paths_label_items_and_children() {
        let node = component("Root", Node::Group { children: vec![
            Node::Repeat { axis: Axis::X, count: 2, child_extent: 1, gap: 0, child: Box::new(component("Post", leaf(), None)) },
            component("Door", leaf(), None),
        ] }, None);
        let r = resolve(&node, size(2, 1, 1)).unwrap();
        let group = &r.children[0];
        assert_eq!(group.path, "Root/body");
        assert_eq!(group.children[0].children[1].path, "Root/body/child[0]/Post[1]");
        assert_eq!(group.children[1].path, "Root/body/child[1]/Door");
        assert_eq!(code(resolve(&component("Big", leaf(), Some(Point::new(3, 1, 1))), size(2, 1, 1))), "component_too_small");
    }

    #[test]
    fn transform_rotates_footprint_and_rejects_overflow() {
        let node = Node::Transform { translation: Point::new(1, 0, 0), rotation: Rotation::R90, child_size: Point::new(3, 1, 1), child: Box::new(leaf()) };
        let r = resolve(&node, size(2, 1, 3)).unwrap();
        assert_eq!(r.children[0].region, size(3, 1, 1));
        assert_eq!(r.children[0].world_transforms.len(), 1);
        let e = resolve(&node, size(2, 1, 2)).unwrap_err();
        assert_eq!(e.diagnostics[0].message, "transformed footprint {'min': [1, 0, 0], 'max': [2, 1, 3]} is outside assigned region");
    }
}
