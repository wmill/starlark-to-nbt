//! Redstone attachment support check (port of `support.py`).
//!
//! Minecraft drops attachable redstone parts (dust, repeaters, comparators,
//! torches, levers, buttons, pressure plates) on the first block update if
//! their supporting block can't hold them. A structure that places them over
//! air is silently broken in-game, so every such part must have a solid block
//! on its attachment side.
//!
//! Support-cell semantics for sparse output:
//! - written with a supporting block: ok
//! - written with a non-supporting block (including carved air): error
//! - unwritten and outside the root box: unknown terrain, ok
//! - unwritten, inside the box, below `ground_level`: buried in terrain, ok
//! - unwritten, inside the box, at or above ground level: air on paste, error
//!
//! Solidity is a conservative denylist, kept verbatim from Python.

use crate::blocks::{BlockId, BlockTable};
use crate::execute::{SparseVolume, Voxel};
use crate::ir::BuildMetadata;
use crate::model::{BlockSpec, Diagnostic, Point, Region};

const DOWN: Point = Point::new(0, -1, 0);
const UP: Point = Point::new(0, 1, 0);

/// Offset from an attachable to its support, opposite its `facing`.
fn behind(facing: &str) -> Option<Point> {
    match facing {
        "south" => Some(Point::new(0, 0, -1)),
        "north" => Some(Point::new(0, 0, 1)),
        "east" => Some(Point::new(-1, 0, 0)),
        "west" => Some(Point::new(1, 0, 0)),
        _ => None,
    }
}

const NEEDS_BELOW: [&str; 6] = [
    "minecraft:redstone_wire",
    "minecraft:repeater",
    "minecraft:comparator",
    "minecraft:redstone_torch",
    "minecraft:torch",
    "minecraft:soul_torch",
];

const WALL_TORCHES: [&str; 3] = ["minecraft:redstone_wall_torch", "minecraft:wall_torch", "minecraft:soul_wall_torch"];

/// Block types that cannot hold an attachable, by exact id ...
const NON_SUPPORTING_TYPES: [&str; 20] = [
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:water",
    "minecraft:lava",
    "minecraft:torch",
    "minecraft:wall_torch",
    "minecraft:redstone_wire",
    "minecraft:repeater",
    "minecraft:comparator",
    "minecraft:lever",
    "minecraft:hopper",
    "minecraft:piston",
    "minecraft:sticky_piston",
    "minecraft:piston_head",
    "minecraft:moving_piston",
    "minecraft:rail",
    "minecraft:ladder",
    "minecraft:lantern",
    "minecraft:soul_lantern",
    "minecraft:chain",
];

/// ... and by suffix (dyed, wood, and material variants in one rule).
const NON_SUPPORTING_SUFFIXES: [&str; 16] = [
    "_torch",
    "_pressure_plate",
    "_button",
    "_sign",
    "_banner",
    "_pane",
    "_fence",
    "_fence_gate",
    "_carpet",
    "_door",
    "_trapdoor",
    "_slab",
    "_stairs",
    "_wall",
    "_rail",
    "_bed",
];

pub fn is_supporting_block(block_type: &str) -> bool {
    !NON_SUPPORTING_TYPES.contains(&block_type) && !NON_SUPPORTING_SUFFIXES.iter().any(|s| block_type.ends_with(s))
}

fn can_support(support_type: &str, attachable_type: &str) -> bool {
    // Vanilla lets pressure plates sit on fence posts, walls, and hoppers.
    if attachable_type.ends_with("_pressure_plate")
        && (support_type.ends_with("_fence") || support_type.ends_with("_wall") || support_type == "minecraft:hopper")
    {
        return true;
    }
    is_supporting_block(support_type)
}

/// Offset from the block to the cell that must support it, if any.
fn support_offset(block: &BlockSpec) -> Option<Point> {
    let t = block.block_type.as_str();
    let state = |key: &str, default: &'static str| block.block_state.get(key).map_or(default, String::as_str);
    if NEEDS_BELOW.contains(&t) || t.ends_with("_pressure_plate") {
        return Some(DOWN);
    }
    if WALL_TORCHES.contains(&t) {
        return behind(state("facing", "north"));
    }
    if t == "minecraft:lever" || t.ends_with("_button") {
        return match state("face", "wall") {
            "floor" => Some(DOWN),
            "ceiling" => Some(UP),
            _ => behind(state("facing", "north")),
        };
    }
    None
}

pub fn support_diagnostics(volume: &SparseVolume, root: Region, metadata: BuildMetadata, blocks: &BlockTable) -> Vec<Diagnostic> {
    // The offset depends only on the block, so compute it once per id.
    let offsets: Vec<Option<Point>> = (0..blocks.len()).map(|i| support_offset(blocks.get(BlockId(i as u32)))).collect();
    let mut attachables: Vec<Point> = volume
        .voxels
        .iter()
        .filter(|(_, v)| offsets[v.block.0 as usize].is_some())
        .map(|(p, _)| *p)
        .collect();
    attachables.sort_unstable_by_key(|p| (p.y, p.z, p.x));
    let mut errors = Vec::new();
    for pos in attachables {
        let voxel = &volume.voxels[&pos];
        let support = pos + offsets[voxel.block.0 as usize].expect("filtered above");
        if let Some(d) = check_support(volume, root, metadata, blocks, pos, voxel, support) {
            errors.push(d);
        }
    }
    errors
}

fn check_support(
    volume: &SparseVolume,
    root: Region,
    metadata: BuildMetadata,
    blocks: &BlockTable,
    pos: Point,
    voxel: &Voxel,
    support: Point,
) -> Option<Diagnostic> {
    let attachable = &blocks.get(voxel.block).block_type;
    let reason = match volume.voxels.get(&support) {
        Some(existing) => {
            let support_type = &blocks.get(existing.block).block_type;
            if can_support(support_type, attachable) {
                return None;
            }
            format!("it rests on {support_type}, which cannot hold it")
        }
        None => {
            if !root.contains_point(support) || support.y < metadata.ground_level {
                return None; // unknown terrain, or buried when pasted at ground level
            }
            "the cell there is unwritten and will be air when pasted".to_owned()
        }
    };
    Some(
        Diagnostic::new(
            "unsupported_block",
            format!(
                "{attachable} at {} needs a solid block at {}, but {reason}; place a supporting block \
                 (e.g. the part's base prop) or move the component",
                pos.list_str(),
                support.list_str()
            ),
            &voxel.provenance.component_path,
        )
        .with_region(voxel.provenance.assigned_region)
        .with_coordinates(pos)
        .with_detail("support", support.to_val()),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::execute::execute;
    use crate::execute::tests::{bounds, op, provenance};
    use crate::ir::Phase;

    fn spec(t: &str, state: &[(&str, &str)]) -> BlockSpec {
        let mut b = BlockSpec::new(t);
        for (k, v) in state {
            b.block_state.insert((*k).into(), (*v).into());
        }
        b
    }

    /// Ported helper from tests/test_support.py: one op per write, in order.
    fn check(writes: &[(Phase, (i32, i32, i32), BlockSpec)], size: (i32, i32, i32), ground_level: i32) -> Vec<Diagnostic> {
        let mut t = BlockTable::new();
        let root = bounds(size.0, size.1, size.2);
        let p = provenance("Test", root);
        let ops: Vec<_> = writes.iter().enumerate().map(|(i, (phase, pos, b))| op(*phase, &[(*pos, t.intern(b.clone()))], &p, i)).collect();
        let v = execute(&ops, root, vec![], &t).unwrap();
        support_diagnostics(&v, root, BuildMetadata { ground_level, stage_delay_ticks: None }, &t)
    }

    fn ok(writes: &[(Phase, (i32, i32, i32), BlockSpec)]) -> bool {
        check(writes, (4, 4, 4), 0).is_empty()
    }

    use Phase::{Carve, Fixture, Structure};

    #[test]
    fn dust_rules() {
        let (stone, dust) = (spec("minecraft:stone", &[]), spec("minecraft:redstone_wire", &[]));
        assert!(ok(&[(Structure, (1, 0, 1), stone.clone()), (Fixture, (1, 1, 1), dust.clone())]));
        let e = check(&[(Fixture, (1, 2, 1), dust.clone())], (4, 4, 4), 0);
        assert_eq!((e[0].component_path.as_str(), e[0].coordinates), ("Test", Some(Point::new(1, 2, 1))));
        assert_eq!(e[0].details["support"].py_repr(), "[1, 1, 1]");
        assert!(check(&[(Fixture, (1, 2, 1), dust.clone())], (4, 4, 4), 3).is_empty(), "terrain below ground level");
        assert!(check(&[(Fixture, (0, 0, 0), dust.clone())], (1, 1, 1), 0).is_empty(), "standalone part at the floor");
        assert!(!ok(&[(Structure, (1, 0, 1), stone.clone()), (Carve, (1, 0, 1), BlockSpec::air()), (Fixture, (1, 1, 1), dust.clone())]));
        let e = check(&[(Structure, (1, 0, 1), stone), (Fixture, (1, 1, 1), spec("minecraft:repeater", &[("facing", "north")])), (Fixture, (1, 2, 1), dust)], (4, 4, 4), 0);
        assert!(e[0].message.contains("rests on minecraft:repeater"), "{}", e[0].message);
    }

    #[test]
    fn torches_levers_buttons_and_plates() {
        let stone = spec("minecraft:stone", &[]);
        let wall_torch = spec("minecraft:redstone_wall_torch", &[("facing", "south"), ("lit", "true")]);
        assert!(ok(&[(Structure, (1, 1, 1), stone.clone()), (Fixture, (1, 1, 2), wall_torch.clone())]));
        assert!(!ok(&[(Fixture, (1, 1, 2), wall_torch)]));
        let plain = spec("minecraft:wall_torch", &[("facing", "east")]);
        assert!(ok(&[(Structure, (1, 1, 1), stone.clone()), (Fixture, (2, 1, 1), plain.clone())]));
        assert!(!ok(&[(Fixture, (2, 1, 1), plain)]));
        let torch = spec("minecraft:torch", &[]);
        assert!(ok(&[(Structure, (1, 0, 1), stone.clone()), (Fixture, (1, 1, 1), torch.clone())]));
        assert!(!ok(&[(Fixture, (1, 2, 1), torch)]));
        assert!(ok(&[(Structure, (1, 0, 1), stone.clone()), (Fixture, (1, 1, 1), spec("minecraft:lever", &[("face", "floor"), ("facing", "south")]))]));
        let button = spec("minecraft:stone_button", &[("face", "wall"), ("facing", "south")]);
        assert!(ok(&[(Structure, (1, 1, 1), stone.clone()), (Fixture, (1, 1, 2), button.clone())]));
        assert!(!ok(&[(Structure, (1, 0, 2), stone.clone()), (Fixture, (1, 1, 2), button)]));
        assert!(!ok(&[(Fixture, (1, 1, 1), spec("minecraft:light_weighted_pressure_plate", &[("power", "0")]))]));
        assert!(ok(&[(Structure, (1, 0, 1), spec("minecraft:oak_fence", &[])), (Fixture, (1, 1, 1), spec("minecraft:stone_pressure_plate", &[]))]));
    }

    #[test]
    fn all_violations_reported_and_non_attachables_ignored() {
        let dust = spec("minecraft:redstone_wire", &[]);
        let e = check(&[(Fixture, (1, 1, 1), dust.clone()), (Fixture, (2, 1, 1), dust)], (4, 4, 4), 0);
        assert_eq!(e.iter().map(|d| d.code).collect::<Vec<_>>(), ["unsupported_block", "unsupported_block"]);
        assert!(ok(&[(Structure, (1, 2, 1), spec("minecraft:redstone_lamp", &[("lit", "false")]))]));
    }
}
