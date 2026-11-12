//! The stages after Starlark evaluation, in order (port of
//! `pipeline._finish_build`): root-size selection, layout, lowering,
//! execute, then the support check and declared validators. Support and
//! validator diagnostics are collected into one error.
//!
//! Output writing lives in `serialize::write_build_outputs`.

use crate::blocks::BlockTable;
use crate::execute::{execute, SparseVolume};
use crate::ir::{BlockOperation, BuildMetadata, Node};
use crate::layout::resolve;
use crate::lowering::lower_all;
use crate::model::{fail, BuildError, Point, Region};
use crate::support::support_diagnostics;
use crate::val::{Dict, Val};
use crate::validators::validator_diagnostics;

#[derive(Debug)]
pub struct BuildResult {
    /// Holds the entities too (`volume.entities`).
    pub volume: SparseVolume,
    pub operations: Vec<BlockOperation>,
    /// Every `BlockId` in `volume` and `operations` indexes this table.
    pub blocks: BlockTable,
    pub metadata: BuildMetadata,
}

/// Python's `int()` on a root-size prop. The CLI coerces `--arg` values to
/// int/float/bool/str, so those are the cases that occur.
fn prop_int(props: &Dict, key: &str) -> Result<i32, BuildError> {
    let bad = || fail("invalid_root_size", format!("{key} prop must be an integer, got {}", props[key].py_repr()), "<root>");
    let value: i64 = match &props[key] {
        Val::Int(i) => *i,
        Val::Bool(b) => i64::from(*b),
        Val::Float(f) if f.is_finite() => f.trunc() as i64,
        Val::Str(s) => s.trim().parse().map_err(|_| bad())?,
        _ => return Err(bad()),
    };
    i32::try_from(value).map_err(|_| bad())
}

/// Python `pipeline._root_size`: `width`/`height`/`length` props (each at
/// least the root's `min_size`), else `min_size`, else `missing_root_size`.
pub fn root_size(node: &Node, props: &Dict) -> Result<Point, BuildError> {
    let min_size = node.min_size();
    if ["width", "height", "length"].iter().all(|k| props.contains_key(*k)) {
        let requested = Point::new(prop_int(props, "width")?, prop_int(props, "height")?, prop_int(props, "length")?);
        return Ok(match min_size {
            Some(m) => Point::new(requested.x.max(m.x), requested.y.max(m.y), requested.z.max(m.z)),
            None => requested,
        });
    }
    min_size.ok_or_else(|| {
        fail("missing_root_size", "root_size is required when width, height, and length props are not all supplied", "<root>")
    })
}

/// Everything after schema validation. `root_size` overrides the size
/// derived from `props`, as Python's `root_size=` argument does.
pub fn build(node: &Node, props: &Dict, root_size_override: Option<Point>) -> Result<BuildResult, BuildError> {
    let size = match root_size_override {
        Some(size) => size,
        None => root_size(node, props)?,
    };
    let root = Region::from_size(size, Point::ZERO).map_err(|m| fail("invalid_box", m, "<root>"))?;
    finish_build(node, root)
}

pub fn finish_build(node: &Node, root: Region) -> Result<BuildResult, BuildError> {
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
    Ok(BuildResult { volume, operations: lowered.operations, blocks: lowered.blocks, metadata })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::val::from_json;

    fn props(json: &str) -> Dict {
        match from_json(json) {
            Val::Dict(d) => d,
            _ => unreachable!(),
        }
    }

    fn component(min_size: Option<Point>) -> Node {
        Node::Component(Box::new(crate::ir::Component {
            name: "C".into(), props: Dict::new(), body: Node::Group { children: vec![] },
            min_size, source: None, metadata: None, validators: vec![],
        }))
    }

    #[test]
    fn root_size_follows_python_rules() {
        let sized = component(Some(Point::new(3, 4, 5)));
        assert_eq!(root_size(&sized, &Dict::new()).unwrap(), Point::new(3, 4, 5));
        assert_eq!(root_size(&sized, &props(r#"{"width": 9, "height": 2, "length": "6"}"#)).unwrap(), Point::new(9, 4, 6));
        assert_eq!(root_size(&component(None), &props(r#"{"width": 2.9, "height": true, "length": 1}"#)).unwrap(), Point::new(2, 1, 1));
        assert_eq!(root_size(&component(None), &props(r#"{"width": 2}"#)).unwrap_err().diagnostics[0].code, "missing_root_size");
        assert_eq!(root_size(&sized, &props(r#"{"width": "x", "height": 1, "length": 1}"#)).unwrap_err().diagnostics[0].code, "invalid_root_size");
        let e = build(&component(None), &Dict::new(), Some(Point::new(0, 1, 1))).unwrap_err();
        assert_eq!((e.diagnostics[0].code, e.diagnostics[0].component_path.as_str()), ("invalid_box", "<root>"));
    }
}
