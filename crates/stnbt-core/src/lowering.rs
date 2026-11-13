//! Flattening the resolved tree into world-space block operations
//! (port of `lowering.py`).
//!
//! Transforms apply innermost first (Python iterates `reversed(transforms)`).
//! A component's provenance is computed once and shared by every leaf under
//! it. A block's world rotation is cached per (source spec, transform stack)
//! and interned, so a fill costs one rotation and one intern, however large.

use std::sync::Arc;

use rustc_hash::{FxHashMap, FxHashSet};

use crate::blocks::{BlockId, BlockTable};
use crate::ir::{BlockOperation, BlockWrite, EntityPlacement, EntitySpec, LoweringResult, Node, OpKind, Phase, ValidatorPlacement};
use crate::layout::ResolvedNode;
use crate::model::{BlockSpec, BuildError, Diagnostic, Point, Provenance, Region, Transform};

type R<T> = Result<T, BuildError>;

fn apply(mut p: Point, transforms: &[Transform]) -> Point {
    for t in transforms.iter().rev() {
        p = t.apply_point(p);
    }
    p
}

/// World bounding box of a local region: transform the corner cells, then
/// take the half-open hull.
fn world_box(region: &Region, transforms: &[Transform]) -> Region {
    if transforms.is_empty() {
        return *region;
    }
    let (lo, hi) = (region.min, region.max - Point::new(1, 1, 1));
    let mut min = Point::new(i32::MAX, i32::MAX, i32::MAX);
    let mut max = Point::new(i32::MIN, i32::MIN, i32::MIN);
    for x in [lo.x, hi.x] {
        for y in [lo.y, hi.y] {
            for z in [lo.z, hi.z] {
                let c = apply(Point::new(x, y, z), transforms);
                min = Point::new(min.x.min(c.x), min.y.min(c.y), min.z.min(c.z));
                max = Point::new(max.x.max(c.x), max.y.max(c.y), max.z.max(c.z));
            }
        }
    }
    Region { min, max: max + Point::new(1, 1, 1) }
}

struct Lowerer {
    blocks: BlockTable,
    /// (source spec address, transform stack address) -> world block.
    rotated: FxHashMap<(usize, usize), BlockId>,
    operations: Vec<BlockOperation>,
    entities: Vec<EntityPlacement>,
    validators: Vec<ValidatorPlacement>,
}

impl Lowerer {
    /// The source `BlockSpec`s live in the IR tree and the transform stacks
    /// in the resolved tree, and both outlive lowering, so their addresses
    /// are stable cache keys.
    fn world_block(&mut self, block: &BlockSpec, transforms: &Arc<[Transform]>) -> BlockId {
        let key = (block as *const BlockSpec as usize, transforms.as_ptr() as usize);
        if let Some(id) = self.rotated.get(&key) {
            return *id;
        }
        let mut spec = block.clone();
        for t in transforms.iter().rev() {
            spec = spec.transformed(t);
        }
        let id = self.blocks.intern(spec);
        self.rotated.insert(key, id);
        id
    }

    fn push_op(&mut self, stage: u8, phase: Phase, kind: OpKind, writes: Vec<BlockWrite>, provenance: &Arc<Provenance>, assembly: Option<String>) {
        let sequence = self.operations.len();
        self.operations.push(BlockOperation { stage, phase, kind, writes, provenance: provenance.clone(), assembly_name: assembly, sequence });
    }

    fn lower(&mut self, node: &ResolvedNode<'_>, owner: Option<&Arc<Provenance>>) -> R<()> {
        let own;
        let mut owner = owner;
        if let Node::Component(c) = node.node {
            own = Arc::new(Provenance {
                component_path: node.path.clone(),
                assigned_region: world_box(&node.region, &node.world_transforms),
                source: c.source.clone(),
            });
            for v in &c.validators {
                let sequence = self.validators.len();
                self.validators.push(ValidatorPlacement { validator: v.clone(), provenance: own.clone(), sequence });
            }
            owner = Some(&own);
        }
        for child in &node.children {
            self.lower(child, owner)?;
        }
        if !node.children.is_empty() {
            return Ok(());
        }
        if matches!(node.node, Node::Group { .. }) {
            return Ok(()); // childless group: nothing to emit
        }
        let fallback;
        let provenance = match owner {
            Some(p) => p,
            None => {
                // No component above this leaf: it owns itself.
                fallback = Arc::new(Provenance {
                    component_path: node.path.clone(),
                    assigned_region: world_box(&node.region, &node.world_transforms),
                    source: None,
                });
                &fallback
            }
        };
        let transforms = &node.world_transforms;
        let world_point = |local: Point| apply(node.region.min + local, transforms);

        match node.node {
            Node::PlaceBlock { pos, block, phase, stage } => {
                let id = self.world_block(block, transforms);
                self.push_op(*stage, *phase, OpKind::PlaceBlock, vec![BlockWrite { pos: world_point(*pos), block: id }], provenance, None);
            }
            Node::PlaceEntity { pos, entity } => {
                let pos = world_point(*pos);
                if !provenance.assigned_region.contains_point(pos) {
                    return Err(Diagnostic::new("entity_component_overflow", "entity anchor is outside its component's assigned region", &provenance.component_path)
                        .with_region(provenance.assigned_region)
                        .with_coordinates(pos)
                        .into());
                }
                let mut yaw = entity.yaw;
                for t in transforms.iter().rev() {
                    yaw = py_mod_360(yaw + f64::from(t.rotation.degrees()));
                }
                let sequence = self.entities.len();
                self.entities.push(EntityPlacement {
                    pos,
                    entity: EntitySpec { entity_type: entity.entity_type.clone(), nbt: entity.nbt.clone(), yaw, pitch: entity.pitch },
                    provenance: provenance.clone(),
                    sequence,
                });
            }
            Node::FillRegion { region, block, phase, stage } => {
                let id = self.world_block(block, transforms);
                let writes = cells(region).map(|p| BlockWrite { pos: world_point(p), block: id }).collect();
                self.push_op(*stage, *phase, OpKind::FillRegion, writes, provenance, None);
            }
            Node::CarveRegion { region, stage } => {
                let writes = cells(region).map(|p| BlockWrite { pos: world_point(p), block: BlockId::AIR }).collect();
                self.push_op(*stage, Phase::Carve, OpKind::CarveRegion, writes, provenance, None);
            }
            Node::PlaceAssembly { pos, name, size, blocks, stage } => {
                let bounds = Region { min: Point::ZERO, max: *size };
                let placed = world_box(&bounds.translated(node.region.min + *pos), transforms);
                if !provenance.assigned_region.contains_box(&placed) {
                    return Err(Diagnostic::new("assembly_overflow", format!("assembly {name} bounds are outside the assigned region"), &provenance.component_path)
                        .with_region(provenance.assigned_region)
                        .with_detail("assemblyRegion", placed.to_val())
                        .into());
                }
                let mut seen = FxHashSet::default();
                let mut writes = Vec::with_capacity(blocks.len());
                for item in blocks {
                    if !seen.insert(item.pos) {
                        return Err(Diagnostic::new("assembly_duplicate", format!("assembly {name} contains duplicate offset {}", item.pos.list_str()), &provenance.component_path).into());
                    }
                    if !bounds.contains_point(item.pos) {
                        return Err(Diagnostic::new("assembly_invalid", format!("assembly block {} is outside declared size", item.pos.list_str()), &provenance.component_path).into());
                    }
                    let id = self.world_block(&item.block, transforms);
                    writes.push(BlockWrite { pos: world_point(*pos + item.pos), block: id });
                }
                self.push_op(*stage, Phase::Fixture, OpKind::PlaceAssembly, writes, provenance, Some(name.clone()));
            }
            Node::Component(_) | Node::Group { .. } | Node::Split { .. } | Node::Inset { .. } | Node::Repeat { .. } | Node::Transform { .. } => {
                unreachable!("layout always gives {} children", node.node.class_name())
            }
        }
        Ok(())
    }
}

/// Python's float `%` with a positive divisor: the result takes the
/// divisor's sign.
fn py_mod_360(value: f64) -> f64 {
    let r = value % 360.0;
    if r < 0.0 {
        r + 360.0
    } else if r == 0.0 {
        0.0 // Python never returns -0.0 here
    } else {
        r
    }
}

/// Local cells in y, z, x order: the write order Python uses.
fn cells(region: &Region) -> impl Iterator<Item = Point> + '_ {
    (region.min.y..region.max.y).flat_map(move |y| {
        (region.min.z..region.max.z).flat_map(move |z| (region.min.x..region.max.x).map(move |x| Point::new(x, y, z)))
    })
}

pub fn lower_all(root: &ResolvedNode<'_>) -> R<LoweringResult> {
    let mut lowerer = Lowerer {
        blocks: BlockTable::new(),
        rotated: FxHashMap::default(),
        operations: Vec::new(),
        entities: Vec::new(),
        validators: Vec::new(),
    };
    lowerer.lower(root, None)?;
    Ok(LoweringResult {
        operations: lowerer.operations,
        entities: lowerer.entities,
        validators: lowerer.validators,
        blocks: lowerer.blocks,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{AssemblyBlock, Component};
    use crate::layout::resolve;
    use crate::model::Rotation;

    fn size(x: i32, y: i32, z: i32) -> Region {
        Region { min: Point::ZERO, max: Point::new(x, y, z) }
    }

    fn component(name: &str, body: Node) -> Node {
        Node::Component(Box::new(Component { name: name.into(), props: Default::default(), body, min_size: None, source: None, metadata: None, validators: vec![] }))
    }

    fn lower(node: &Node, root: Region) -> R<LoweringResult> {
        lower_all(&resolve(node, root)?)
    }

    // Ported from tests/test_transform_execution.py.
    #[test]
    fn fixture_phase_fill_region_lowers_into_fixture_operations() {
        let node = component("Carpet", Node::FillRegion { region: size(2, 1, 2), block: BlockSpec::new("minecraft:red_carpet"), phase: Phase::Fixture, stage: 0 });
        let out = lower(&node, size(2, 1, 2)).unwrap();
        assert_eq!(out.operations.iter().map(|o| o.phase).collect::<Vec<_>>(), [Phase::Fixture]);
        let writes: Vec<_> = out.operations[0].writes.iter().map(|w| w.pos).collect();
        assert_eq!(writes, [Point::new(0, 0, 0), Point::new(1, 0, 0), Point::new(0, 0, 1), Point::new(1, 0, 1)]);
    }

    #[test]
    fn declared_assembly_bounds_must_fit_even_when_a_cell_is_unoccupied() {
        let node = component("Door", Node::PlaceAssembly {
            pos: Point::ZERO, name: "door".into(), size: Point::new(1, 2, 1),
            blocks: vec![AssemblyBlock { pos: Point::ZERO, block: BlockSpec::new("minecraft:oak_door") }], stage: 0,
        });
        let e = lower(&node, size(1, 1, 1)).unwrap_err();
        assert_eq!(e.diagnostics[0].code, "assembly_overflow");
        assert_eq!(e.diagnostics[0].details["assemblyRegion"].py_repr(), "{'min': [0, 0, 0], 'max': [1, 2, 1]}");
    }

    #[test]
    fn rotation_moves_cells_rotates_states_and_turns_entities() {
        let mut stairs = BlockSpec::new("minecraft:oak_stairs");
        stairs.block_state.insert("facing".into(), "south".into());
        let inner = component("Inner", Node::Group { children: vec![
            Node::PlaceBlock { pos: Point::new(2, 0, 0), block: stairs, phase: Phase::Structure, stage: 0 },
            Node::PlaceEntity { pos: Point::new(0, 0, 0), entity: EntitySpec { entity_type: "minecraft:pig".into(), nbt: None, yaw: 300.0, pitch: 0.0 } },
        ] });
        let root = component("Root", Node::Transform { translation: Point::new(1, 0, 1), rotation: Rotation::R90, child_size: Point::new(3, 1, 2), child: Box::new(inner) });
        let out = lower(&root, size(4, 1, 4)).unwrap();
        let op = &out.operations[0];
        // (2,0,0) in a 3x1x2 child under R90 -> (d-1-z, y, x) = (1, 0, 2), then +(1,0,1).
        assert_eq!(op.writes[0].pos, Point::new(2, 0, 3));
        assert_eq!(out.blocks.get(op.writes[0].block).block_state["facing"], "west");
        assert_eq!(op.provenance.component_path, "Root/body/Inner");
        assert_eq!(op.provenance.assigned_region, Region { min: Point::new(1, 0, 1), max: Point::new(3, 1, 4) });
        assert_eq!(out.entities[0].entity.yaw, 30.0);
    }

    #[test]
    fn fills_share_one_interned_block_and_assemblies_check_offsets() {
        let node = component("C", Node::Group { children: vec![
            Node::FillRegion { region: size(3, 1, 1), block: BlockSpec::new("minecraft:stone"), phase: Phase::Structure, stage: 0 },
            Node::PlaceBlock { pos: Point::new(0, 1, 0), block: BlockSpec::new("minecraft:stone"), phase: Phase::Structure, stage: 0 },
            Node::CarveRegion { region: size(1, 1, 1), stage: 0 },
        ] });
        let out = lower(&node, size(3, 2, 1)).unwrap();
        assert_eq!(out.blocks.len(), 2); // air + stone
        assert_eq!(out.operations.iter().map(|o| o.sequence).collect::<Vec<_>>(), [0, 1, 2]);
        assert_eq!(out.operations[2].writes[0].block, BlockId::AIR);

        let dup = component("D", Node::PlaceAssembly { pos: Point::ZERO, name: "bed".into(), size: Point::new(2, 1, 1), blocks: vec![
            AssemblyBlock { pos: Point::ZERO, block: BlockSpec::new("minecraft:red_bed") },
            AssemblyBlock { pos: Point::ZERO, block: BlockSpec::new("minecraft:red_bed") },
        ], stage: 0 });
        assert_eq!(lower(&dup, size(2, 1, 1)).unwrap_err().diagnostics[0].message, "assembly bed contains duplicate offset [0, 0, 0]");
    }

    #[test]
    fn python_float_modulo() {
        assert_eq!(py_mod_360(-30.0), 330.0);
        assert_eq!(py_mod_360(450.0), 90.0);
        assert!(py_mod_360(-360.0).is_sign_positive());
    }
}
