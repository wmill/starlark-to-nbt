//! Validated component IR (port of `ir.py`'s `Node` union).
//!
//! `Node::to_val` reproduces Python's `pipeline._jsonable(node)` exactly:
//! the `component-ir.json` debug output and the schema parity tests both
//! depend on it.

use crate::model::{Axis, BlockSpec, Point, Region, Rotation, SourceRef};
use crate::val::{Dict, Val};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SizeExpr {
    Fixed(i32),
    Fill,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct BuildMetadata {
    pub ground_level: i32,
    /// Server ticks between install stages, if the script set it.
    pub stage_delay_ticks: Option<i32>,
}

/// Highest `stage=` a script may use. Stage 0 is the default.
pub const MAX_STAGE: u8 = 63;

impl BuildMetadata {
    pub fn y_offset(&self) -> i32 {
        -self.ground_level
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ValidatorSpec {
    DoorSupportedOnBothSides { assembly: String },
}

/// Execution phase. `PlaceBlock`/`FillRegion` only ever carry
/// `Structure` or `Fixture`; `Carve` is implied by `CarveRegion`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Phase {
    Structure = 0,
    Carve = 1,
    Fixture = 2,
}

impl Phase {
    /// The Starlark-facing phase string (`"structure"` / `"fixture"`).
    pub fn as_str(self) -> &'static str {
        match self {
            Phase::Structure => "structure",
            Phase::Carve => "carve",
            Phase::Fixture => "fixture",
        }
    }

    /// The `Phase` IntEnum member name, as the debug JSON prints it.
    pub fn name(self) -> &'static str {
        match self {
            Phase::Structure => "STRUCTURE",
            Phase::Carve => "CARVE",
            Phase::Fixture => "FIXTURE",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct EntitySpec {
    pub entity_type: String,
    pub nbt: Option<Dict>,
    pub yaw: f64,
    pub pitch: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AssemblyBlock {
    pub pos: Point,
    pub block: BlockSpec,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Component {
    pub name: String,
    pub props: Dict,
    pub body: Node,
    pub min_size: Option<Point>,
    pub source: Option<SourceRef>,
    pub metadata: Option<BuildMetadata>,
    pub validators: Vec<ValidatorSpec>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Node {
    Component(Box<Component>),
    Group { children: Vec<Node> },
    Split { axis: Axis, sizes: Vec<SizeExpr>, children: Vec<Node> },
    /// Low/high amounts indexed by `Axis::index()`.
    Inset { amounts: [(i32, i32); 3], child: Box<Node> },
    Repeat { axis: Axis, count: i32, child_extent: i32, gap: i32, child: Box<Node> },
    Transform { translation: Point, rotation: Rotation, child_size: Point, child: Box<Node> },
    /// `stage` orders installation across stages (see execute.rs).
    PlaceBlock { pos: Point, block: BlockSpec, phase: Phase, stage: u8 },
    PlaceEntity { pos: Point, entity: EntitySpec },
    FillRegion { region: Region, block: BlockSpec, phase: Phase, stage: u8 },
    CarveRegion { region: Region, stage: u8 },
    PlaceAssembly { pos: Point, name: String, size: Point, blocks: Vec<AssemblyBlock>, stage: u8 },
}

impl Node {
    /// Python class name, used as a layout path segment for non-components.
    pub fn class_name(&self) -> &'static str {
        match self {
            Node::Component(_) => "Component",
            Node::Group { .. } => "Group",
            Node::Split { .. } => "Split",
            Node::Inset { .. } => "Inset",
            Node::Repeat { .. } => "Repeat",
            Node::Transform { .. } => "TransformNode",
            Node::PlaceBlock { .. } => "PlaceBlock",
            Node::PlaceEntity { .. } => "PlaceEntity",
            Node::FillRegion { .. } => "FillRegion",
            Node::CarveRegion { .. } => "CarveRegion",
            Node::PlaceAssembly { .. } => "PlaceAssembly",
        }
    }

    /// `getattr(node, "min_size", None)`: only components declare one.
    pub fn min_size(&self) -> Option<Point> {
        match self {
            Node::Component(c) => c.min_size,
            _ => None,
        }
    }

    /// Python `pipeline._jsonable(node)`.
    pub fn to_val(&self) -> Val {
        match self {
            Node::Component(c) => tagged("Component", vec![
                ("name", Val::Str(c.name.clone())),
                ("props", Val::Dict(c.props.clone())),
                ("body", c.body.to_val()),
                ("min_size", opt(c.min_size.map(Point::to_val))),
                ("source", opt(c.source.as_ref().map(source_val))),
                ("metadata", opt(c.metadata.map(|m| {
                    let mut fields = vec![("ground_level", int(m.ground_level))];
                    if let Some(ticks) = m.stage_delay_ticks {
                        fields.push(("stage_delay_ticks", int(ticks)));
                    }
                    tagged("BuildMetadata", fields)
                }))),
                ("validators", Val::List(c.validators.iter().map(validator_val).collect())),
            ]),
            Node::Group { children } => tagged("Group", vec![("children", nodes(children))]),
            Node::Split { axis, sizes, children } => tagged("Split", vec![
                ("axis", Val::Str(axis.as_str().into())),
                ("sizes", Val::List(sizes.iter().map(|s| match s {
                    SizeExpr::Fixed(v) => tagged("Fixed", vec![("value", int(*v))]),
                    SizeExpr::Fill => tagged("Fill", vec![]),
                }).collect())),
                ("children", nodes(children)),
            ]),
            Node::Inset { amounts, child } => {
                // `_jsonable` stringifies the Axis-keyed dict with str(Axis.X).
                let amounts: Dict = Axis::ALL
                    .iter()
                    .map(|a| {
                        let (lo, hi) = amounts[a.index()];
                        (a.py_str().to_owned(), Val::List(vec![int(lo), int(hi)]))
                    })
                    .collect();
                tagged("Inset", vec![("amounts", Val::Dict(amounts)), ("child", child.to_val())])
            }
            Node::Repeat { axis, count, child_extent, gap, child } => tagged("Repeat", vec![
                ("axis", Val::Str(axis.as_str().into())),
                ("count", int(*count)),
                ("child_extent", int(*child_extent)),
                ("gap", int(*gap)),
                ("child", child.to_val()),
            ]),
            Node::Transform { translation, rotation, child_size, child } => tagged("TransformNode", vec![
                ("translation", translation.to_val()),
                ("rotation_y", int(rotation.degrees())),
                ("child_size", child_size.to_val()),
                ("child", child.to_val()),
            ]),
            Node::PlaceBlock { pos, block, phase, stage } => staged(tagged("PlaceBlock", vec![
                ("pos", pos.to_val()),
                ("block", block_val(block)),
                ("phase", Val::Str(phase.as_str().into())),
            ]), *stage),
            Node::PlaceEntity { pos, entity } => tagged("PlaceEntity", vec![
                ("pos", pos.to_val()),
                ("entity", tagged("EntitySpec", vec![
                    ("entity_type", Val::Str(entity.entity_type.clone())),
                    ("nbt", opt(entity.nbt.clone().map(Val::Dict))),
                    ("yaw", Val::Float(entity.yaw)),
                    ("pitch", Val::Float(entity.pitch)),
                ])),
            ]),
            Node::FillRegion { region, block, phase, stage } => staged(tagged("FillRegion", vec![
                ("box", region.to_val()),
                ("block", block_val(block)),
                ("phase", Val::Str(phase.as_str().into())),
            ]), *stage),
            Node::CarveRegion { region, stage } => staged(tagged("CarveRegion", vec![("box", region.to_val())]), *stage),
            Node::PlaceAssembly { pos, name, size, blocks, stage } => staged(tagged("PlaceAssembly", vec![
                ("pos", pos.to_val()),
                ("name", Val::Str(name.clone())),
                ("size", size.to_val()),
                ("blocks", Val::List(blocks.iter().map(|b| tagged("AssemblyBlock", vec![
                    ("pos", b.pos.to_val()),
                    ("block", block_val(&b.block)),
                ])).collect())),
            ]), *stage),
        }
    }
}

/// Adds `stage` to a leaf's debug value only when it isn't the default, so
/// unstaged builds keep their existing `component-ir.json`.
fn staged(mut value: Val, stage: u8) -> Val {
    if stage != 0 {
        if let Val::Dict(d) = &mut value {
            d.insert("stage".into(), Val::Int(stage.into()));
        }
    }
    value
}

fn int(v: i32) -> Val {
    Val::Int(v.into())
}

fn opt(v: Option<Val>) -> Val {
    v.unwrap_or(Val::Null)
}

fn nodes(children: &[Node]) -> Val {
    Val::List(children.iter().map(Node::to_val).collect())
}

fn tagged(kind: &str, fields: Vec<(&str, Val)>) -> Val {
    let mut d = Dict::with_capacity(fields.len() + 1);
    d.insert("kind".into(), Val::Str(kind.into()));
    for (k, v) in fields {
        d.insert(k.into(), v);
    }
    Val::Dict(d)
}

fn source_val(s: &SourceRef) -> Val {
    tagged("SourceRef", vec![
        ("file", Val::Str(s.file.clone())),
        ("line", opt(s.line.map(int))),
        ("column", opt(s.column.map(int))),
    ])
}

fn validator_val(v: &ValidatorSpec) -> Val {
    match v {
        ValidatorSpec::DoorSupportedOnBothSides { assembly } => {
            tagged("DoorSupportedOnBothSides", vec![("assembly", Val::Str(assembly.clone()))])
        }
    }
}

pub(crate) fn block_val(b: &BlockSpec) -> Val {
    tagged("BlockSpec", vec![
        ("block_type", Val::Str(b.block_type.clone())),
        ("block_state", Val::Dict(b.block_state.iter().map(|(k, v)| (k.clone(), Val::Str(v.clone()))).collect())),
        ("block_nbt", opt(b.block_nbt.clone().map(Val::Dict))),
    ])
}

// ---- Lowered operations (lowering -> execute) ----

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OpKind {
    PlaceBlock,
    FillRegion,
    CarveRegion,
    PlaceAssembly,
}

impl OpKind {
    pub fn as_str(self) -> &'static str {
        match self {
            OpKind::PlaceBlock => "place_block",
            OpKind::FillRegion => "fill_region",
            OpKind::CarveRegion => "carve_region",
            OpKind::PlaceAssembly => "place_assembly",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BlockWrite {
    pub pos: Point,
    pub block: crate::blocks::BlockId,
}

#[derive(Clone, Debug)]
pub struct BlockOperation {
    /// Install stage: operations run in (stage, phase, sequence) order.
    pub stage: u8,
    pub phase: Phase,
    pub kind: OpKind,
    pub writes: Vec<BlockWrite>,
    /// Shared by every operation of one component.
    pub provenance: std::sync::Arc<crate::model::Provenance>,
    pub assembly_name: Option<String>,
    pub sequence: usize,
}

#[derive(Clone, Debug)]
pub struct EntityPlacement {
    pub pos: Point,
    pub entity: EntitySpec,
    pub provenance: std::sync::Arc<crate::model::Provenance>,
    pub sequence: usize,
}

#[derive(Clone, Debug)]
pub struct ValidatorPlacement {
    pub validator: ValidatorSpec,
    pub provenance: std::sync::Arc<crate::model::Provenance>,
    pub sequence: usize,
}

#[derive(Clone, Debug)]
pub struct LoweringResult {
    pub operations: Vec<BlockOperation>,
    pub entities: Vec<EntityPlacement>,
    pub validators: Vec<ValidatorPlacement>,
    /// Every block id in `operations` indexes this table.
    pub blocks: crate::blocks::BlockTable,
}
