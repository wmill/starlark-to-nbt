//! Opt-in post-execution validators declared by components (port of
//! `validators.py`). Today there is one: `door_supported_on_both_sides`.
//!
//! It finds the named door assemblies in the declaring component's subtree.
//! For each door half it checks that both side jambs are solid and that the
//! front and back cells are clear. Double doors check only their outer jambs.

use crate::blocks::BlockTable;
use crate::execute::SparseVolume;
use crate::ir::{BlockOperation, BlockWrite, BuildMetadata, ValidatorPlacement, ValidatorSpec};
use crate::model::{BlockSpec, Diagnostic, Point, Region};
use crate::support::is_supporting_block;
use crate::val::{py_str_repr, Val};

const AIR_TYPES: [&str; 3] = ["minecraft:air", "minecraft:cave_air", "minecraft:void_air"];

fn front_of(facing: &str) -> Option<Point> {
    match facing {
        "north" => Some(Point::new(0, 0, -1)),
        "south" => Some(Point::new(0, 0, 1)),
        "east" => Some(Point::new(1, 0, 0)),
        "west" => Some(Point::new(-1, 0, 0)),
        _ => None,
    }
}

fn neg(p: Point) -> Point {
    Point::new(-p.x, -p.y, -p.z)
}

/// Rotate a horizontal direction a quarter turn: Python's `Point(f.z, 0, -f.x)`.
fn side_of(front: Point) -> Point {
    Point::new(front.z, 0, -front.x)
}

struct Ctx<'a> {
    volume: &'a SparseVolume,
    root: Region,
    metadata: BuildMetadata,
    blocks: &'a BlockTable,
}

impl Ctx<'_> {
    fn has_support(&self, p: Point) -> bool {
        match self.volume.voxels.get(&p) {
            Some(v) => is_supporting_block(&self.blocks.get(v.block).block_type),
            None => !self.root.contains_point(p) || p.y < self.metadata.ground_level,
        }
    }

    fn is_clear(&self, p: Point) -> bool {
        match self.volume.voxels.get(&p) {
            Some(v) => AIR_TYPES.contains(&self.blocks.get(v.block).block_type.as_str()),
            None => !self.root.contains_point(p) || p.y >= self.metadata.ground_level,
        }
    }
}

pub fn validator_diagnostics(
    validators: &[ValidatorPlacement],
    operations: &[BlockOperation],
    volume: &SparseVolume,
    root: Region,
    metadata: BuildMetadata,
    blocks: &BlockTable,
) -> Vec<Diagnostic> {
    let ctx = Ctx { volume, root, metadata, blocks };
    let mut ordered: Vec<&ValidatorPlacement> = validators.iter().collect();
    ordered.sort_by_key(|v| v.sequence);
    let mut errors = Vec::new();
    for placement in ordered {
        let ValidatorSpec::DoorSupportedOnBothSides { assembly } = &placement.validator;
        validate_doors(&ctx, placement, assembly, operations, &mut errors);
    }
    errors
}

fn in_scope(path: &str, scope: &str) -> bool {
    path == scope || (path.starts_with(scope) && path[scope.len()..].starts_with('/'))
}

fn door_details(assembly: &str, extra: &[(&'static str, Val)]) -> Vec<(&'static str, Val)> {
    let mut out = vec![("validator", Val::Str("door_supported_on_both_sides".into())), ("assembly", Val::Str(assembly.into()))];
    out.extend(extra.iter().cloned());
    out
}

fn with_details(mut d: Diagnostic, details: Vec<(&'static str, Val)>) -> Diagnostic {
    for (k, v) in details {
        d = d.with_detail(k, v);
    }
    d
}

fn validate_doors(ctx: &Ctx<'_>, placement: &ValidatorPlacement, assembly: &str, operations: &[BlockOperation], errors: &mut Vec<Diagnostic>) {
    let scope = &placement.provenance.component_path;
    let targets: Vec<&BlockOperation> = operations
        .iter()
        .filter(|op| op.assembly_name.as_deref() == Some(assembly) && in_scope(&op.provenance.component_path, scope))
        .collect();
    if targets.is_empty() {
        errors.push(with_details(
            Diagnostic::new(
                "validator_no_targets",
                format!("door validator found no assembly named {} in its component subtree", py_str_repr(assembly)),
                scope,
            )
            .with_source(placement.provenance.source.clone())
            .with_region(placement.provenance.assigned_region),
            door_details(assembly, &[]),
        ));
        return;
    }
    for op in targets {
        let prov = &op.provenance;
        let base = |code: &'static str, message: String| {
            Diagnostic::new(code, message, &prov.component_path).with_source(prov.source.clone()).with_region(prov.assigned_region)
        };
        let Some((columns, facing)) = door_halves(op, ctx.blocks) else {
            let mut d = base("invalid_validator_target", format!("assembly {} is not a matching single or double door", py_str_repr(assembly)));
            if let Some(first) = op.writes.first() {
                d = d.with_coordinates(first.pos);
            }
            errors.push(with_details(d, door_details(assembly, &[])));
            continue;
        };
        let occupied: Vec<Point> = columns.iter().flat_map(|(lo, hi)| [*lo, *hi]).collect();
        let front = front_of(facing).expect("door_halves checked facing");
        let left = side_of(front);
        let right = Point::new(-left.x, 0, -left.z);
        for (lower, upper) in &columns {
            for (height, anchor) in [("lower", *lower), ("upper", *upper)] {
                for (side, offset) in [("left", left), ("right", right)] {
                    let support = anchor + offset;
                    if occupied.contains(&support) || ctx.has_support(support) {
                        continue;
                    }
                    let d = base("door_not_supported", format!("{height} half has no solid {side} jamb at {}", support.list_str()));
                    errors.push(with_details(d.with_coordinates(*lower), door_details(assembly, &[
                        ("half", Val::Str(height.into())),
                        ("side", Val::Str(side.into())),
                        ("support", support.to_val()),
                    ])));
                }
                for (direction, offset) in [("front", front), ("back", neg(front))] {
                    let clearance = anchor + offset;
                    if ctx.is_clear(clearance) {
                        continue;
                    }
                    let d = base("doorway_obstructed", format!("{height} half is obstructed at its {direction} cell {}", clearance.list_str()));
                    errors.push(with_details(d.with_coordinates(*lower), door_details(assembly, &[
                        ("half", Val::Str(height.into())),
                        ("direction", Val::Str(direction.into())),
                        ("obstruction", clearance.to_val()),
                    ])));
                }
            }
        }
    }
}

/// The (lower, upper) columns and facing of a single or double door, or
/// `None` if the assembly isn't one.
fn door_halves<'b>(op: &BlockOperation, blocks: &'b BlockTable) -> Option<(Vec<(Point, Point)>, &'b str)> {
    let n = op.writes.len();
    if n != 2 && n != 4 {
        return None;
    }
    let spec = |w: &BlockWrite| -> &'b BlockSpec { blocks.get(w.block) };
    let state = |w: &BlockWrite, key: &str| spec(w).block_state.get(key).map(String::as_str);
    let lowers: Vec<&BlockWrite> = op.writes.iter().filter(|w| state(w, "half") == Some("lower")).collect();
    let uppers: Vec<&BlockWrite> = op.writes.iter().filter(|w| state(w, "half") == Some("upper")).collect();
    if lowers.len() != n / 2 || uppers.len() != lowers.len() {
        return None;
    }
    let facing = state(lowers[0], "facing")?;
    let material = &spec(lowers[0]).block_type;
    if front_of(facing).is_none() || !material.ends_with("_door") {
        return None;
    }
    let mut columns = Vec::with_capacity(lowers.len());
    for lower in &lowers {
        let above = lower.pos + Point::new(0, 1, 0);
        let upper = uppers.iter().find(|u| u.pos == above)?;
        if &spec(lower).block_type != material
            || &spec(upper).block_type != material
            || state(lower, "facing") != Some(facing)
            || state(upper, "facing") != Some(facing)
        {
            return None;
        }
        if lowers.len() == 2 && ["hinge", "open", "powered"].iter().any(|k| state(lower, k) != state(upper, k)) {
            return None;
        }
        columns.push((lower.pos, upper.pos));
    }
    if lowers.len() == 2 {
        let side = side_of(front_of(facing)?);
        let (a, b) = (lowers[0].pos, lowers[1].pos);
        if b != a + side && b != a + neg(side) {
            return None;
        }
        let mut hinges = [state(lowers[0], "hinge"), state(lowers[1], "hinge")];
        hinges.sort();
        if hinges != [Some("left"), Some("right")] {
            return None;
        }
    }
    Some((columns, facing))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::execute::execute;
    use crate::execute::tests::{bounds, provenance};
    use crate::ir::{OpKind, Phase};
    use std::sync::Arc;

    fn door(t: &mut BlockTable, facing: &str, half: &str, hinge: &str, facing_override: Option<&str>) -> crate::blocks::BlockId {
        let mut b = BlockSpec::new("minecraft:oak_door");
        for (k, v) in [("facing", facing_override.unwrap_or(facing)), ("hinge", hinge), ("open", "false"), ("powered", "false"), ("half", half)] {
            b.block_state.insert(k.into(), v.into());
        }
        t.intern(b)
    }

    struct Fixture {
        t: BlockTable,
        owner: Arc<crate::model::Provenance>,
    }

    impl Fixture {
        fn new() -> Fixture {
            Fixture { t: BlockTable::new(), owner: provenance("Root/body/Door", bounds(7, 4, 7)) }
        }

        fn structure(&mut self, points: &[Point], block: &str) -> BlockOperation {
            let id = self.t.intern(BlockSpec::new(block));
            BlockOperation { stage: 0, phase: Phase::Structure, kind: OpKind::FillRegion, writes: points.iter().map(|p| BlockWrite { pos: *p, block: id }).collect(), provenance: self.owner.clone(), assembly_name: None, sequence: 0 }
        }

        fn door_op(&mut self, facing: &str) -> BlockOperation {
            let (lo, hi) = (door(&mut self.t, facing, "lower", "left", None), door(&mut self.t, facing, "upper", "left", None));
            BlockOperation { stage: 0, phase: Phase::Fixture, kind: OpKind::PlaceAssembly, writes: vec![
                BlockWrite { pos: Point::new(3, 1, 3), block: lo }, BlockWrite { pos: Point::new(3, 2, 3), block: hi },
            ], provenance: self.owner.clone(), assembly_name: Some("door".into()), sequence: 1 }
        }

        /// Returns the double door op plus its front and side vectors.
        fn double_door(&mut self, facing: &str, defect: Option<&str>) -> (BlockOperation, Point, Point) {
            let front = front_of(facing).unwrap();
            let side = side_of(front);
            let mut writes = vec![];
            for column in 0..2 {
                let mut pos = Point::new(3, 1, 3) + if column == 1 { side } else { Point::ZERO };
                if column == 1 && defect == Some("separated") {
                    pos = pos + side;
                }
                for (height, half) in [(0, "lower"), (1, "upper")] {
                    let hinge = if column == 0 || defect == Some("hinges") { "left" } else { "right" };
                    let over = (column == 1 && height == 1 && defect == Some("mismatched_half")).then_some("up");
                    writes.push(BlockWrite { pos: pos + Point::new(0, height, 0), block: door(&mut self.t, facing, half, hinge, over) });
                }
            }
            (BlockOperation { stage: 0, phase: Phase::Fixture, kind: OpKind::PlaceAssembly, writes, provenance: self.owner.clone(), assembly_name: Some("door".into()), sequence: 1 }, front, side)
        }

        fn run(&self, ops: &[BlockOperation], ground_level: i32) -> Vec<&'static str> {
            let root = bounds(7, 4, 7);
            let v = execute(ops, root, vec![], &self.t).unwrap();
            let placement = ValidatorPlacement { validator: ValidatorSpec::DoorSupportedOnBothSides { assembly: "door".into() }, provenance: provenance("Root", root), sequence: 0 };
            validator_diagnostics(&[placement], ops, &v, root, BuildMetadata { ground_level, stage_delay_ticks: None }, &self.t).iter().map(|d| d.code).collect()
        }
    }

    fn pts(v: &[(i32, i32, i32)]) -> Vec<Point> {
        v.iter().map(|(x, y, z)| Point::new(*x, *y, *z)).collect()
    }

    // Ported from tests/test_validators.py.
    #[test]
    fn single_doors() {
        let mut f = Fixture::new();
        let jambs = f.structure(&pts(&[(2, 1, 3), (2, 2, 3), (4, 1, 3), (4, 2, 3)]), "minecraft:stone");
        let d = f.door_op("south");
        assert!(f.run(&[jambs, d], 0).is_empty());

        let mut f = Fixture::new();
        let jambs = f.structure(&pts(&[(2, 1, 3), (2, 2, 3), (4, 1, 3)]), "minecraft:stone");
        let block = f.structure(&pts(&[(3, 2, 4)]), "minecraft:stone");
        let d = f.door_op("south");
        assert_eq!(f.run(&[jambs, block, d], 0), ["door_not_supported", "doorway_obstructed"]);

        let mut f = Fixture::new();
        let jambs = f.structure(&pts(&[(3, 1, 2), (3, 2, 2), (3, 1, 4), (3, 2, 4)]), "minecraft:stone");
        let d = f.door_op("east");
        assert!(f.run(&[jambs, d], 0).is_empty(), "rotated facing");

        let mut f = Fixture::new();
        let passage = f.structure(&pts(&[(3, 1, 2), (3, 1, 4), (3, 2, 2), (3, 2, 4)]), "minecraft:air");
        let d = f.door_op("south");
        assert!(f.run(&[passage, d], 4).is_empty(), "buried jambs are terrain");
    }

    #[test]
    fn malformed_out_of_scope_and_missing_targets() {
        let mut f = Fixture::new();
        let stone = f.t.intern(BlockSpec::new("minecraft:stone"));
        let malformed = BlockOperation { stage: 0, phase: Phase::Fixture, kind: OpKind::PlaceAssembly, writes: vec![BlockWrite { pos: Point::new(1, 1, 1), block: stone }], provenance: f.owner.clone(), assembly_name: Some("door".into()), sequence: 0 };
        let outside = BlockOperation { stage: 0, phase: Phase::Fixture, kind: OpKind::PlaceAssembly, writes: vec![BlockWrite { pos: Point::new(5, 1, 5), block: stone }], provenance: provenance("Other", bounds(7, 4, 7)), assembly_name: Some("door".into()), sequence: 2 };
        assert_eq!(f.run(&[malformed, outside], 0), ["invalid_validator_target"]);
        assert_eq!(f.run(&[], 0), ["validator_no_targets"]);
        assert!(in_scope("Root/body", "Root") && in_scope("Root", "Root") && !in_scope("Rooted", "Root"));
    }

    #[test]
    fn double_doors() {
        for facing in ["north", "east", "south", "west"] {
            let mut f = Fixture::new();
            let (d, front, side) = f.double_door(facing, None);
            let origin = Point::new(3, 1, 3);
            let mut jamb_points = vec![];
            for offset in [Point::new(-side.x, 0, -side.z), side + side] {
                for h in 0..2 {
                    jamb_points.push(origin + offset + Point::new(0, h, 0));
                }
            }
            let jambs = f.structure(&jamb_points, "minecraft:stone");
            assert!(f.run(&[jambs, d.clone()], 0).is_empty(), "{facing}");
            let partial = f.structure(&jamb_points[..3], "minecraft:stone");
            assert!(f.run(&[partial, d.clone()], 0).iter().all(|c| *c == "door_not_supported"));
            for column in [Point::ZERO, side] {
                for direction in [front, neg(front)] {
                    let mut points = jamb_points.clone();
                    points.push(origin + column + direction);
                    let ops = [f.structure(&points, "minecraft:stone"), d.clone()];
                    assert_eq!(f.run(&ops, 0), ["doorway_obstructed"], "{facing}");
                }
            }
        }
        for defect in ["separated", "hinges", "mismatched_half"] {
            let mut f = Fixture::new();
            let (d, _, _) = f.double_door("south", Some(defect));
            assert_eq!(f.run(&[d], 0), ["invalid_validator_target"], "{defect}");
        }
    }
}
