//! The stages after Starlark evaluation, in order (port of
//! `pipeline._finish_build`): layout, lowering, execute, then the support
//! check and declared validators. Support and validator diagnostics are
//! collected into one error.
//!
//! Output writing lives in `serialize::write_build_outputs`; root-size
//! selection (`_root_size`) joins in Phase 5.

use crate::blocks::BlockTable;
use crate::execute::{execute, SparseVolume};
use crate::ir::{BlockOperation, BuildMetadata, Node};
use crate::layout::resolve;
use crate::lowering::lower_all;
use crate::model::{BuildError, Region};
use crate::support::support_diagnostics;
use crate::validators::validator_diagnostics;

#[derive(Debug)]
pub struct BuildResult {
    /// Holds the entities too (`volume.entities`).
    pub volume: SparseVolume,
    pub operations: Vec<BlockOperation>,
    /// Every `BlockId` in `volume` and `operations` indexes this table.
    pub blocks: BlockTable,
    pub metadata: BuildMetadata,
    /// `resolved.json` content, kept only when `finish_build` is asked for
    /// debug output (the resolved tree borrows the IR, so it isn't stored).
    pub resolved: Option<crate::val::Val>,
}

pub fn finish_build(node: &Node, root: Region, debug: bool) -> Result<BuildResult, BuildError> {
    let resolved = resolve(node, root)?;
    let lowered = lower_all(&resolved)?;
    let volume = execute(&lowered.operations, root, lowered.entities, &lowered.blocks)?;
    let metadata = match node {
        Node::Component(c) => c.metadata.unwrap_or_default(),
        _ => BuildMetadata::default(),
    };
    let mut diagnostics = support_diagnostics(&volume, root, metadata, &lowered.blocks);
    diagnostics.extend(validator_diagnostics(&lowered.validators, &lowered.operations, &volume, root, metadata, &lowered.blocks));
    if !diagnostics.is_empty() {
        return Err(BuildError::new(diagnostics));
    }
    let resolved = debug.then(|| resolved.to_val());
    Ok(BuildResult { volume, operations: lowered.operations, blocks: lowered.blocks, metadata, resolved })
}
