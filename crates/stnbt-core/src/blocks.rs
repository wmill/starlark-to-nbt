//! Block interning: every distinct `BlockSpec` gets a small integer id.
//!
//! Operations and voxels carry `BlockId`s, so fills don't clone a spec per
//! cell and execute's identical-rewrite check is an integer compare.
//!
//! Identity is the block type, the *sorted* state, and the exact nbt. State
//! order is ignored because Python's dict equality ignores it, and rotation
//! reorders connection keys (a rotated fence and a directly written one must
//! still count as the same block). Nbt compares on its exact repr, so `1` vs
//! `1.0`, or a different key order, makes a different block. The
//! compatibility scope in docs/rust-core-plan.md allows that.

use rustc_hash::FxHashMap;

use crate::model::BlockSpec;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct BlockId(pub u32);

impl BlockId {
    /// `minecraft:air` with no state or nbt (Python's `AIR`), always id 0.
    pub const AIR: BlockId = BlockId(0);
}

type BlockKey = (String, Vec<(String, String)>, Option<String>);

#[derive(Clone, Debug)]
pub struct BlockTable {
    specs: Vec<BlockSpec>,
    index: FxHashMap<BlockKey, BlockId>,
}

impl Default for BlockTable {
    fn default() -> Self {
        BlockTable::new()
    }
}

impl BlockTable {
    pub fn new() -> BlockTable {
        let mut table = BlockTable { specs: Vec::new(), index: FxHashMap::default() };
        let air = table.intern(BlockSpec::air());
        debug_assert_eq!(air, BlockId::AIR);
        table
    }

    fn key(spec: &BlockSpec) -> BlockKey {
        let (block_type, state) = spec.key();
        let nbt = spec.block_nbt.as_ref().map(|d| crate::val::Val::Dict(d.clone()).py_repr());
        (block_type, state, nbt)
    }

    pub fn intern(&mut self, spec: BlockSpec) -> BlockId {
        let key = BlockTable::key(&spec);
        if let Some(id) = self.index.get(&key) {
            return *id;
        }
        let id = BlockId(u32::try_from(self.specs.len()).expect("fewer than 2^32 distinct blocks"));
        self.specs.push(spec);
        self.index.insert(key, id);
        id
    }

    pub fn get(&self, id: BlockId) -> &BlockSpec {
        &self.specs[id.0 as usize]
    }

    pub fn len(&self) -> usize {
        self.specs.len()
    }

    pub fn is_empty(&self) -> bool {
        self.specs.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interning_ignores_state_order_and_reserves_air() {
        let mut table = BlockTable::new();
        let mut a = BlockSpec::new("minecraft:oak_fence");
        a.block_state.insert("south".into(), "true".into());
        a.block_state.insert("west".into(), "true".into());
        let mut b = BlockSpec::new("minecraft:oak_fence");
        b.block_state.insert("west".into(), "true".into());
        b.block_state.insert("south".into(), "true".into());
        assert_eq!(table.intern(a), table.intern(b));
        assert_eq!(table.intern(BlockSpec::air()), BlockId::AIR);
        assert_ne!(table.intern(BlockSpec::new("minecraft:stone")), BlockId::AIR);
        assert_eq!(table.len(), 3);
    }
}
