//! Applying operations to a sparse volume (port of `execute.py`).
//!
//! Operations run in (stage, phase, sequence) order. Within a stage:
//! STRUCTURE, then CARVE, then FIXTURE. In STRUCTURE, rewriting a cell with
//! the identical block is allowed and a differing block is a
//! `block_conflict`. FIXTURE rejects any overlap with a non-air cell. CARVE
//! overwrites. A write may replace any cell last written in an earlier
//! stage (an observer replacing its placeholder). An operation's writes are
//! all validated before any is applied, so assemblies are atomic, and all of
//! one operation's errors are reported together.
//!
//! When more than one stage is used, `execute_staged` also returns one
//! layer per stage: the cells that stage wrote, as they stood when it
//! finished. Placing the layers in order on successive ticks reproduces
//! the final volume.

use std::sync::Arc;

use rustc_hash::{FxHashMap, FxHashSet};

use crate::blocks::{BlockId, BlockTable};
use crate::ir::{BlockOperation, EntityPlacement, Phase};
use crate::model::{BuildError, Diagnostic, Point, Provenance, Region};
use crate::val::Val;

#[derive(Clone, Debug)]
pub struct Voxel {
    pub block: BlockId,
    pub provenance: Arc<Provenance>,
    pub phase: Phase,
    pub stage: u8,
}

/// The cells one install stage writes. Bounds are always the root box, so
/// every layer shares one coordinate frame.
#[derive(Clone, Debug)]
pub struct StageLayer {
    pub stage: u8,
    pub volume: SparseVolume,
}

#[derive(Clone, Debug)]
pub struct SparseVolume {
    pub bounds: Region,
    pub voxels: FxHashMap<Point, Voxel>,
    pub entities: Vec<EntityPlacement>,
}

impl SparseVolume {
    pub fn new(bounds: Region) -> SparseVolume {
        SparseVolume { bounds, voxels: FxHashMap::default(), entities: Vec::new() }
    }

    /// Unwritten cells read as air.
    pub fn block_at(&self, p: Point) -> BlockId {
        self.voxels.get(&p).map_or(BlockId::AIR, |v| v.block)
    }

    /// Written cells in (y, z, x) order, the order serialization and the
    /// support scan use.
    pub fn sorted_points(&self) -> Vec<Point> {
        let mut points: Vec<Point> = self.voxels.keys().copied().collect();
        points.sort_unstable_by_key(|p| (p.y, p.z, p.x));
        points
    }
}

pub fn execute(
    operations: &[BlockOperation],
    root: Region,
    entities: Vec<EntityPlacement>,
    blocks: &BlockTable,
) -> Result<SparseVolume, BuildError> {
    execute_staged(operations, root, entities, blocks).map(|(volume, _)| volume)
}

/// `execute`, plus the per-stage layers when operations use more than one
/// stage (otherwise the layer list is empty). Entities ride on the last
/// layer, after every block is in place.
pub fn execute_staged(
    operations: &[BlockOperation],
    root: Region,
    entities: Vec<EntityPlacement>,
    blocks: &BlockTable,
) -> Result<(SparseVolume, Vec<StageLayer>), BuildError> {
    for item in &entities {
        if !root.contains_point(item.pos) {
            return Err(Diagnostic::new("entity_root_overflow", "entity anchor is outside root bounds", &item.provenance.component_path)
                .with_region(root)
                .with_coordinates(item.pos)
                .into());
        }
    }
    let mut volume = SparseVolume::new(root);
    volume.entities = entities;
    volume.voxels.reserve(operations.iter().map(|o| o.writes.len()).sum());
    let mut order: Vec<&BlockOperation> = operations.iter().collect();
    order.sort_by_key(|op| (op.stage, op.phase, op.sequence));
    let staged = order.first().zip(order.last()).is_some_and(|(a, b)| a.stage != b.stage);
    let mut layers: Vec<StageLayer> = Vec::new();
    for op in order {
        execute_operation(&mut volume, op, blocks)?;
        if staged {
            if layers.last().is_none_or(|l| l.stage != op.stage) {
                layers.push(StageLayer { stage: op.stage, volume: SparseVolume::new(root) });
            }
            let layer = &mut layers.last_mut().expect("pushed above").volume;
            for write in &op.writes {
                layer.voxels.insert(write.pos, volume.voxels[&write.pos].clone());
            }
        }
    }
    if let Some(last) = layers.last_mut() {
        last.volume.entities = volume.entities.clone();
    }
    Ok((volume, layers))
}

pub fn execute_operation(volume: &mut SparseVolume, op: &BlockOperation, blocks: &BlockTable) -> Result<(), BuildError> {
    let path = &op.provenance.component_path;
    let mut errors = Vec::new();
    // Only multi-write operations can repeat a cell.
    let mut seen = FxHashSet::default();
    for write in &op.writes {
        if op.writes.len() > 1 && !seen.insert(write.pos) {
            errors.push(Diagnostic::new("operation_duplicate", "operation writes the same cell more than once", path).with_coordinates(write.pos));
            continue;
        }
        if !volume.bounds.contains_point(write.pos) {
            errors.push(Diagnostic::new("root_overflow", "block is outside root bounds", path)
                .with_region(volume.bounds)
                .with_coordinates(write.pos));
            continue;
        }
        if !op.provenance.assigned_region.contains_point(write.pos) {
            errors.push(Diagnostic::new("component_overflow", "block is outside its component's assigned region", path)
                .with_region(op.provenance.assigned_region)
                .with_coordinates(write.pos));
            continue;
        }
        if let Some(existing) = volume.voxels.get(&write.pos) {
            if existing.block != BlockId::AIR && existing.stage == op.stage {
                // Identical structural rewrites are harmless (fills share
                // corners and edges); fixtures may never overlap.
                let conflict = match op.phase {
                    Phase::Structure => existing.block != write.block,
                    Phase::Fixture => true,
                    Phase::Carve => false,
                };
                if conflict {
                    errors.push(collision(op, write.pos, existing, blocks));
                }
            }
        }
    }
    if !errors.is_empty() {
        return Err(BuildError::new(errors));
    }
    for write in &op.writes {
        volume.voxels.insert(write.pos, Voxel { block: write.block, provenance: op.provenance.clone(), phase: op.phase, stage: op.stage });
    }
    Ok(())
}

fn collision(op: &BlockOperation, point: Point, existing: &Voxel, blocks: &BlockTable) -> Diagnostic {
    Diagnostic::new(
        "block_conflict",
        format!("cannot overwrite {} from {}", blocks.get(existing.block).block_type, existing.provenance.component_path),
        &op.provenance.component_path,
    )
    .with_coordinates(point)
    .with_detail("existingComponent", Val::Str(existing.provenance.component_path.clone()))
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::ir::{BlockWrite, OpKind};
    use crate::model::BlockSpec;

    pub fn bounds(x: i32, y: i32, z: i32) -> Region {
        Region { min: Point::ZERO, max: Point::new(x, y, z) }
    }

    pub fn provenance(path: &str, region: Region) -> Arc<Provenance> {
        Arc::new(Provenance { component_path: path.into(), assigned_region: region, source: None })
    }

    pub fn op(phase: Phase, writes: &[((i32, i32, i32), BlockId)], prov: &Arc<Provenance>, sequence: usize) -> BlockOperation {
        BlockOperation {
            stage: 0,
            phase,
            kind: OpKind::PlaceBlock,
            writes: writes.iter().map(|((x, y, z), b)| BlockWrite { pos: Point::new(*x, *y, *z), block: *b }).collect(),
            provenance: prov.clone(),
            assembly_name: None,
            sequence,
        }
    }

    fn codes(r: Result<SparseVolume, BuildError>) -> Vec<&'static str> {
        r.unwrap_err().diagnostics.iter().map(|d| d.code).collect()
    }

    fn staged(stage: u8, phase: Phase, writes: &[((i32, i32, i32), BlockId)], prov: &Arc<Provenance>, sequence: usize) -> BlockOperation {
        BlockOperation { stage, ..op(phase, writes, prov, sequence) }
    }

    #[test]
    fn later_stages_replace_earlier_cells_and_get_their_own_layers() {
        let mut t = BlockTable::new();
        let (glass, observer, stone) = (
            t.intern(BlockSpec::new("minecraft:glass")),
            t.intern(BlockSpec::new("minecraft:observer")),
            t.intern(BlockSpec::new("minecraft:stone")),
        );
        let p = provenance("Door", bounds(4, 4, 4));
        // Source order is reversed on purpose: stage order wins.
        let (volume, layers) = execute_staged(&[
            staged(2, Phase::Fixture, &[((1, 1, 1), stone)], &p, 0),
            staged(1, Phase::Structure, &[((1, 1, 1), observer)], &p, 1),
            staged(0, Phase::Structure, &[((1, 1, 1), glass), ((2, 1, 1), glass)], &p, 2),
        ], bounds(4, 4, 4), vec![], &t).unwrap();
        assert_eq!(volume.block_at(Point::new(1, 1, 1)), stone);
        assert_eq!(layers.iter().map(|l| l.stage).collect::<Vec<_>>(), [0, 1, 2]);
        assert_eq!(layers[0].volume.voxels.len(), 2);
        assert_eq!(layers[0].volume.block_at(Point::new(1, 1, 1)), glass);
        assert_eq!((layers[1].volume.voxels.len(), layers[1].volume.block_at(Point::new(1, 1, 1))), (1, observer));
        assert_eq!(layers[2].volume.bounds, bounds(4, 4, 4));
    }

    #[test]
    fn conflicts_still_apply_within_a_stage_and_single_stage_builds_have_no_layers() {
        let mut t = BlockTable::new();
        let (stone, planks) = (t.intern(BlockSpec::new("minecraft:stone")), t.intern(BlockSpec::new("minecraft:oak_planks")));
        let p = provenance("Test", bounds(4, 4, 4));
        let e = execute_staged(&[staged(3, Phase::Structure, &[((1, 1, 1), stone)], &p, 0), staged(3, Phase::Structure, &[((1, 1, 1), planks)], &p, 1)], bounds(4, 4, 4), vec![], &t).unwrap_err();
        assert_eq!(e.diagnostics[0].code, "block_conflict");
        let (_, layers) = execute_staged(&[staged(3, Phase::Structure, &[((1, 1, 1), stone)], &p, 0)], bounds(4, 4, 4), vec![], &t).unwrap();
        assert!(layers.is_empty());
    }

    #[test]
    fn entities_outside_the_root_are_rejected() {
        use crate::ir::{EntityPlacement, EntitySpec};
        let p = provenance("Pen", bounds(4, 1, 1));
        let pig = EntityPlacement { pos: Point::new(3, 0, 0), entity: EntitySpec { entity_type: "minecraft:pig".into(), nbt: None, yaw: 0.0, pitch: 0.0 }, provenance: p, sequence: 0 };
        let e = execute(&[], bounds(2, 1, 1), vec![pig], &BlockTable::new()).unwrap_err();
        assert_eq!((e.diagnostics[0].code, e.diagnostics[0].coordinates), ("entity_root_overflow", Some(Point::new(3, 0, 0))));
    }

    // Ported from tests/test_transform_execution.py.
    #[test]
    fn structure_allows_identical_rewrites_but_rejects_differing_blocks() {
        let mut t = BlockTable::new();
        let (stone, planks) = (t.intern(BlockSpec::new("minecraft:stone")), t.intern(BlockSpec::new("minecraft:oak_planks")));
        let p = provenance("Test", bounds(4, 4, 4));
        let v = execute(&[
            op(Phase::Structure, &[((1, 1, 1), stone), ((2, 1, 1), stone)], &p, 0),
            op(Phase::Structure, &[((2, 1, 1), stone), ((3, 1, 1), stone)], &p, 1),
        ], bounds(4, 4, 4), vec![], &t).unwrap();
        assert_eq!(v.block_at(Point::new(2, 1, 1)), stone);
        let e = execute(&[op(Phase::Structure, &[((1, 1, 1), stone)], &p, 0), op(Phase::Structure, &[((1, 1, 1), planks)], &p, 1)], bounds(4, 4, 4), vec![], &t).unwrap_err();
        assert_eq!(e.diagnostics[0].code, "block_conflict");
        assert_eq!(e.diagnostics[0].message, "cannot overwrite minecraft:stone from Test");
    }

    #[test]
    fn fixture_rejects_even_identical_overlaps() {
        let mut t = BlockTable::new();
        let lantern = t.intern(BlockSpec::new("minecraft:lantern"));
        let p = provenance("Test", bounds(4, 4, 4));
        assert_eq!(codes(execute(&[op(Phase::Fixture, &[((1, 1, 1), lantern)], &p, 0), op(Phase::Fixture, &[((1, 1, 1), lantern)], &p, 1)], bounds(4, 4, 4), vec![], &t)), ["block_conflict"]);
    }

    #[test]
    fn carve_then_fixture_is_allowed_but_fixture_over_solid_is_not() {
        let mut t = BlockTable::new();
        let stone = t.intern(BlockSpec::new("minecraft:stone"));
        let mut door = BlockSpec::new("minecraft:oak_door");
        door.block_state.insert("half".into(), "lower".into());
        let door = t.intern(door);
        let p = provenance("Test", bounds(4, 4, 4));
        // Sequence order is deliberately reversed: phase order wins.
        let v = execute(&[
            op(Phase::Fixture, &[((1, 1, 1), door)], &p, 0),
            op(Phase::Carve, &[((1, 1, 1), BlockId::AIR)], &p, 1),
            op(Phase::Structure, &[((1, 1, 1), stone)], &p, 2),
        ], bounds(4, 4, 4), vec![], &t).unwrap();
        assert_eq!(v.block_at(Point::new(1, 1, 1)), door);
        assert_eq!(codes(execute(&[op(Phase::Structure, &[((1, 1, 1), stone)], &p, 0), op(Phase::Fixture, &[((1, 1, 1), door)], &p, 1)], bounds(4, 4, 4), vec![], &t)), ["block_conflict"]);
    }

    #[test]
    fn operations_are_atomic_and_report_every_error() {
        let mut t = BlockTable::new();
        let (stone, door) = (t.intern(BlockSpec::new("minecraft:stone")), t.intern(BlockSpec::new("minecraft:oak_door")));
        let p = provenance("Test", bounds(4, 4, 4));
        let mut v = SparseVolume::new(bounds(4, 4, 4));
        execute_operation(&mut v, &op(Phase::Structure, &[((1, 2, 1), stone)], &p, 0), &t).unwrap();
        let assembly = op(Phase::Fixture, &[((1, 1, 1), door), ((1, 2, 1), door)], &p, 1);
        assert!(execute_operation(&mut v, &assembly, &t).is_err());
        assert_eq!(v.block_at(Point::new(1, 1, 1)), BlockId::AIR);
        assert_eq!(v.block_at(Point::new(1, 2, 1)), stone);

        let small = provenance("Small", bounds(1, 1, 1));
        let bad = op(Phase::Structure, &[((0, 0, 0), stone), ((0, 0, 0), stone), ((9, 0, 0), stone), ((1, 0, 0), stone)], &small, 0);
        assert_eq!(codes(execute(&[bad], bounds(4, 4, 4), vec![], &t)), ["operation_duplicate", "root_overflow", "component_overflow"]);
    }
}
