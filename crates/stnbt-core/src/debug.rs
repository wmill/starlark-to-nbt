//! The `--debug-dir` stage dumps, as `Val` trees with the same shape as
//! Python's `operations_to_dict`, `entities_to_dict`, and
//! `BlockSpec.to_dict`. (`resolved.json` is `ResolvedNode::to_val`, and
//! `component-ir.json` is `Node::to_val`.)

use crate::blocks::BlockTable;
use crate::ir::{BlockOperation, EntityPlacement};
use crate::model::BlockSpec;
use crate::val::{Dict, Val};

fn s(v: &str) -> Val {
    Val::Str(v.to_owned())
}

/// Python `BlockSpec.to_dict()`: sorted state, `blockNbt` only when present.
pub fn block_to_val(block: &BlockSpec) -> Val {
    let mut d = Dict::with_capacity(3);
    d.insert("blockType".into(), s(&block.block_type));
    let (_, sorted) = block.key();
    d.insert("blockState".into(), Val::Dict(sorted.into_iter().map(|(k, v)| (k, Val::Str(v))).collect()));
    if let Some(nbt) = &block.block_nbt {
        d.insert("blockNbt".into(), Val::Dict(nbt.clone()));
    }
    Val::Dict(d)
}

pub fn operations_to_val(operations: &[BlockOperation], blocks: &BlockTable) -> Val {
    // Writes of one op share few blocks; convert each block id once.
    let block_vals: Vec<Val> = (0..blocks.len()).map(|i| block_to_val(blocks.get(crate::blocks::BlockId(i as u32)))).collect();
    Val::List(operations.iter().map(|op| {
        let mut d = Dict::with_capacity(7);
        d.insert("phase".into(), s(op.phase.name()));
        if op.stage != 0 {
            d.insert("stage".into(), Val::Int(op.stage.into()));
        }
        d.insert("kind".into(), s(op.kind.as_str()));
        d.insert("sequence".into(), Val::Int(op.sequence as i64));
        d.insert("componentPath".into(), s(&op.provenance.component_path));
        d.insert("assignedRegion".into(), op.provenance.assigned_region.to_val());
        d.insert("assembly".into(), op.assembly_name.as_deref().map_or(Val::Null, s));
        d.insert("writes".into(), Val::List(op.writes.iter().map(|w| {
            let mut wd = Dict::with_capacity(2);
            wd.insert("pos".into(), w.pos.to_val());
            wd.insert("block".into(), block_vals[w.block.0 as usize].clone());
            Val::Dict(wd)
        }).collect()));
        Val::Dict(d)
    }).collect())
}

pub fn entities_to_val(entities: &[EntityPlacement]) -> Val {
    Val::List(entities.iter().map(|e| {
        let mut d = Dict::with_capacity(8);
        d.insert("sequence".into(), Val::Int(e.sequence as i64));
        d.insert("pos".into(), e.pos.to_val());
        d.insert("entityType".into(), s(&e.entity.entity_type));
        d.insert("yaw".into(), Val::Float(e.entity.yaw));
        d.insert("pitch".into(), Val::Float(e.entity.pitch));
        d.insert("nbt".into(), e.entity.nbt.clone().map_or(Val::Null, Val::Dict));
        d.insert("componentPath".into(), s(&e.provenance.component_path));
        d.insert("assignedRegion".into(), e.provenance.assigned_region.to_val());
        Val::Dict(d)
    }).collect())
}
