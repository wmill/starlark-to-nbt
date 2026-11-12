//! Shared geometry, block, transform, and diagnostic types (port of `model.py`).
//!
//! Coordinates: +X east, +Y up, +Z south. Regions are half-open.
//! Python's `Box` is `Region` here so it does not shadow `std::boxed::Box`.

use std::borrow::Cow;
use std::fmt;

use indexmap::IndexMap;

use crate::val::{Dict, Val};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Axis {
    X,
    Y,
    Z,
}

impl Axis {
    pub const ALL: [Axis; 3] = [Axis::X, Axis::Y, Axis::Z];

    pub fn parse(value: &str) -> Option<Axis> {
        match value {
            "x" => Some(Axis::X),
            "y" => Some(Axis::Y),
            "z" => Some(Axis::Z),
            _ => None,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Axis::X => "x",
            Axis::Y => "y",
            Axis::Z => "z",
        }
    }

    /// Python's `str(Axis.X)` (a plain `(str, Enum)` mixin prints the member name).
    pub fn py_str(self) -> &'static str {
        match self {
            Axis::X => "Axis.X",
            Axis::Y => "Axis.Y",
            Axis::Z => "Axis.Z",
        }
    }

    pub fn index(self) -> usize {
        self as usize
    }
}

/// Ordering is lexicographic (x, y, z), matching the Python `order=True` dataclass.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Point {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

impl Point {
    pub const ZERO: Point = Point { x: 0, y: 0, z: 0 };

    pub const fn new(x: i32, y: i32, z: i32) -> Point {
        Point { x, y, z }
    }

    pub fn get(self, axis: Axis) -> i32 {
        match axis {
            Axis::X => self.x,
            Axis::Y => self.y,
            Axis::Z => self.z,
        }
    }

    pub fn with(self, axis: Axis, value: i32) -> Point {
        let mut out = self;
        match axis {
            Axis::X => out.x = value,
            Axis::Y => out.y = value,
            Axis::Z => out.z = value,
        }
        out
    }

    pub fn to_array(self) -> [i32; 3] {
        [self.x, self.y, self.z]
    }

    /// `[x, y, z]`, as Python's `to_list()` prints in messages.
    pub fn list_str(self) -> String {
        format!("[{}, {}, {}]", self.x, self.y, self.z)
    }

    /// Python dataclass repr, e.g. `Point(x=0, y=1, z=2)`.
    pub fn py_repr(self) -> String {
        format!("Point(x={}, y={}, z={})", self.x, self.y, self.z)
    }

    pub fn to_val(self) -> Val {
        Val::List(vec![Val::Int(self.x.into()), Val::Int(self.y.into()), Val::Int(self.z.into())])
    }
}

impl std::ops::Add for Point {
    type Output = Point;
    fn add(self, o: Point) -> Point {
        Point::new(self.x + o.x, self.y + o.y, self.z + o.z)
    }
}

impl std::ops::Sub for Point {
    type Output = Point;
    fn sub(self, o: Point) -> Point {
        Point::new(self.x - o.x, self.y - o.y, self.z - o.z)
    }
}

/// Half-open axis-aligned box with strictly positive extents (Python `Box`).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Region {
    pub min: Point,
    pub max: Point,
}

impl Region {
    /// Validating constructor. The error text is Python's `ValueError` message.
    pub fn new(min: Point, max: Point) -> Result<Region, String> {
        let region = Region { min, max };
        if min.x >= max.x || min.y >= max.y || min.z >= max.z {
            return Err(format!("box must have positive extents: {}", region.py_repr()));
        }
        Ok(region)
    }

    pub fn from_size(size: Point, origin: Point) -> Result<Region, String> {
        Region::new(origin, origin + size)
    }

    pub fn size(&self) -> Point {
        self.max - self.min
    }

    pub fn extent(&self, axis: Axis) -> i32 {
        self.max.get(axis) - self.min.get(axis)
    }

    pub fn contains_point(&self, p: Point) -> bool {
        self.min.x <= p.x && p.x < self.max.x
            && self.min.y <= p.y && p.y < self.max.y
            && self.min.z <= p.z && p.z < self.max.z
    }

    pub fn contains_box(&self, other: &Region) -> bool {
        self.min.x <= other.min.x && other.max.x <= self.max.x
            && self.min.y <= other.min.y && other.max.y <= self.max.y
            && self.min.z <= other.min.z && other.max.z <= self.max.z
    }

    /// Translation preserves extents, so no re-validation is needed.
    pub fn translated(&self, offset: Point) -> Region {
        Region { min: self.min + offset, max: self.max + offset }
    }

    pub fn py_repr(&self) -> String {
        format!("Box(min={}, max={})", self.min.py_repr(), self.max.py_repr())
    }

    /// `{'min': [..], 'max': [..]}` as Python prints `Box.to_dict()` in messages.
    pub fn dict_str(&self) -> String {
        format!("{{'min': {}, 'max': {}}}", self.min.list_str(), self.max.list_str())
    }

    pub fn to_val(&self) -> Val {
        let mut d = Dict::new();
        d.insert("min".into(), self.min.to_val());
        d.insert("max".into(), self.max.to_val());
        Val::Dict(d)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rotation {
    R0,
    R90,
    R180,
    R270,
}

impl Rotation {
    pub fn from_degrees(degrees: i64) -> Option<Rotation> {
        match degrees {
            0 => Some(Rotation::R0),
            90 => Some(Rotation::R90),
            180 => Some(Rotation::R180),
            270 => Some(Rotation::R270),
            _ => None,
        }
    }

    pub fn degrees(self) -> i32 {
        self.quarter_turns() as i32 * 90
    }

    pub fn quarter_turns(self) -> u8 {
        self as u8
    }

    pub fn is_quarter(self) -> bool {
        matches!(self, Rotation::R90 | Rotation::R270)
    }
}

/// Facing names in clockwise quarter-turn order.
pub const FACING_ORDER: [&str; 4] = ["south", "west", "north", "east"];

/// A normalized quarter-turn about the source box, followed by translation.
/// Unlike Python, `source_size` is mandatory: every transform the pipeline
/// builds has one, and rotation without it is meaningless.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Transform {
    pub translation: Point,
    pub rotation: Rotation,
    pub source_size: Point,
}

impl Transform {
    pub fn footprint_size(&self) -> Point {
        let s = self.source_size;
        if self.rotation.is_quarter() {
            Point::new(s.z, s.y, s.x)
        } else {
            s
        }
    }

    pub fn apply_point(&self, p: Point) -> Point {
        let (w, d) = (self.source_size.x, self.source_size.z);
        let rotated = match self.rotation {
            Rotation::R0 => p,
            Rotation::R90 => Point::new(d - 1 - p.z, p.y, p.x),
            Rotation::R180 => Point::new(w - 1 - p.x, p.y, d - 1 - p.z),
            Rotation::R270 => Point::new(p.z, p.y, w - 1 - p.x),
        };
        rotated + self.translation
    }

    pub fn rotate_facing<'a>(&self, facing: &'a str) -> &'a str {
        match FACING_ORDER.iter().position(|f| *f == facing) {
            Some(i) => FACING_ORDER[(i + self.rotation.quarter_turns() as usize) % 4],
            None => facing,
        }
    }

    pub fn rotate_axis<'a>(&self, axis: &'a str) -> &'a str {
        match (self.rotation.is_quarter(), axis) {
            (true, "x") => "z",
            (true, "z") => "x",
            _ => axis,
        }
    }

    /// Sign-style 0–15 rotation. Non-integer values pass through unchanged.
    /// Python's `int()` also accepts surrounding whitespace, which is kept;
    /// its rarer forms (`1_0`, non-ASCII digits) are not.
    pub fn rotate_sixteenth<'a>(&self, rotation: &'a str) -> Cow<'a, str> {
        match rotation.trim().parse::<i128>() {
            Ok(value) => {
                let turned = (value + 4 * self.rotation.quarter_turns() as i128).rem_euclid(16);
                Cow::Owned(turned.to_string())
            }
            Err(_) => Cow::Borrowed(rotation),
        }
    }
}

pub type BlockState = IndexMap<String, String>;

#[derive(Clone, Debug, PartialEq)]
pub struct BlockSpec {
    pub block_type: String,
    pub block_state: BlockState,
    /// Block-entity data (e.g. sign text), serialized per block instance and
    /// deliberately excluded from `key()`: the palette is only Name+Properties.
    pub block_nbt: Option<Dict>,
}

impl BlockSpec {
    pub fn new(block_type: impl Into<String>) -> BlockSpec {
        BlockSpec { block_type: block_type.into(), block_state: BlockState::new(), block_nbt: None }
    }

    pub fn air() -> BlockSpec {
        BlockSpec::new("minecraft:air")
    }

    pub fn is_air(&self) -> bool {
        // Python compares against `AIR == BlockSpec("minecraft:air")`, so
        // state or nbt on an air block makes it not-AIR.
        self.block_type == "minecraft:air" && self.block_state.is_empty() && self.block_nbt.is_none()
    }

    pub fn transformed(&self, t: &Transform) -> BlockSpec {
        let mut state = BlockState::with_capacity(self.block_state.len());
        for (key, value) in &self.block_state {
            // Multi-face blocks (fences, panes, walls, vines) key their
            // connections by direction: rotate the key, keep the value.
            state.insert(t.rotate_facing(key).to_owned(), value.clone());
        }
        if let Some(facing) = state.get_mut("facing") {
            *facing = t.rotate_facing(facing).to_owned();
        }
        if let Some(axis) = state.get_mut("axis") {
            *axis = t.rotate_axis(axis).to_owned();
        }
        if let Some(rotation) = state.get_mut("rotation") {
            *rotation = t.rotate_sixteenth(rotation).into_owned();
        }
        BlockSpec { block_type: self.block_type.clone(), block_state: state, block_nbt: self.block_nbt.clone() }
    }

    /// Palette key: type plus sorted state pairs.
    pub fn key(&self) -> (String, Vec<(String, String)>) {
        let mut pairs: Vec<(String, String)> =
            self.block_state.iter().map(|(k, v)| (k.clone(), v.clone())).collect();
        pairs.sort();
        (self.block_type.clone(), pairs)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourceRef {
    pub file: String,
    pub line: Option<i32>,
    pub column: Option<i32>,
}

impl SourceRef {
    pub fn file(file: impl Into<String>) -> SourceRef {
        SourceRef { file: file.into(), line: None, column: None }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Provenance {
    pub component_path: String,
    pub assigned_region: Region,
    pub source: Option<SourceRef>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Diagnostic {
    pub code: &'static str,
    pub message: String,
    pub component_path: String,
    pub source: Option<SourceRef>,
    pub region: Option<Region>,
    pub coordinates: Option<Point>,
    pub details: Dict,
}

impl Diagnostic {
    pub fn new(code: &'static str, message: impl Into<String>, component_path: impl Into<String>) -> Diagnostic {
        Diagnostic {
            code,
            message: message.into(),
            component_path: component_path.into(),
            source: None,
            region: None,
            coordinates: None,
            details: Dict::new(),
        }
    }

    pub fn with_source(mut self, source: Option<SourceRef>) -> Diagnostic {
        self.source = source;
        self
    }

    pub fn with_region(mut self, region: Region) -> Diagnostic {
        self.region = Some(region);
        self
    }

    pub fn with_coordinates(mut self, point: Point) -> Diagnostic {
        self.coordinates = Some(point);
        self
    }

    pub fn with_detail(mut self, key: &str, value: Val) -> Diagnostic {
        self.details.insert(key.to_owned(), value);
        self
    }
}

/// Matches Python's `Diagnostic.__str__`: `code: path (file:line): message`.
impl fmt::Display for Diagnostic {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.component_path)?;
        if let Some(source) = &self.source {
            write!(f, " ({}", source.file)?;
            if let Some(line) = source.line {
                write!(f, ":{line}")?;
            }
            write!(f, ")")?;
        }
        write!(f, ": {}", self.message)
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct BuildError {
    pub diagnostics: Vec<Diagnostic>,
}

impl BuildError {
    pub fn new(diagnostics: Vec<Diagnostic>) -> BuildError {
        BuildError { diagnostics }
    }
}

impl From<Diagnostic> for BuildError {
    fn from(d: Diagnostic) -> BuildError {
        BuildError { diagnostics: vec![d] }
    }
}

impl fmt::Display for BuildError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for (i, d) in self.diagnostics.iter().enumerate() {
            if i > 0 {
                writeln!(f)?;
            }
            write!(f, "{d}")?;
        }
        Ok(())
    }
}

impl std::error::Error for BuildError {}

/// Python's `fail(code, message, path)`.
pub fn fail(code: &'static str, message: impl Into<String>, path: impl Into<String>) -> BuildError {
    Diagnostic::new(code, message, path).into()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(pairs: &[(&str, &str)]) -> BlockState {
        pairs.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect()
    }

    fn block(t: &str, pairs: &[(&str, &str)]) -> BlockSpec {
        BlockSpec { block_type: t.into(), block_state: state(pairs), block_nbt: None }
    }

    fn rotate(b: &BlockSpec, degrees: i64) -> BlockSpec {
        let t = Transform {
            translation: Point::ZERO,
            rotation: Rotation::from_degrees(degrees).unwrap(),
            source_size: Point::new(3, 1, 3),
        };
        b.transformed(&t)
    }

    // Ported from tests/test_rotation_states.py.
    #[test]
    fn axis_swaps_on_quarter_turns_only() {
        let log = block("minecraft:oak_log", &[("axis", "x")]);
        assert_eq!(rotate(&log, 90).block_state["axis"], "z");
        assert_eq!(rotate(&log, 180).block_state["axis"], "x");
        assert_eq!(rotate(&log, 270).block_state["axis"], "z");
        assert_eq!(rotate(&block("minecraft:oak_log", &[("axis", "y")]), 90).block_state["axis"], "y");
    }

    #[test]
    fn sixteenth_rotation_advances_by_four_per_quarter_turn() {
        let sign = block("minecraft:oak_sign", &[("rotation", "1")]);
        assert_eq!(rotate(&sign, 90).block_state["rotation"], "5");
        assert_eq!(rotate(&sign, 180).block_state["rotation"], "9");
        assert_eq!(rotate(&sign, 270).block_state["rotation"], "13");
        assert_eq!(rotate(&block("minecraft:oak_sign", &[("rotation", "14")]), 90).block_state["rotation"], "2");
        assert_eq!(rotate(&block("minecraft:oak_sign", &[("rotation", "big")]), 90).block_state["rotation"], "big");
    }

    #[test]
    fn multi_face_connection_keys_rotate_with_block() {
        let pane = block("minecraft:glass_pane", &[("east", "true"), ("west", "true"), ("waterlogged", "false")]);
        assert_eq!(rotate(&pane, 90).block_state, state(&[("north", "true"), ("south", "true"), ("waterlogged", "false")]));
        let fence = block("minecraft:oak_fence", &[("east", "true"), ("south", "true")]);
        assert_eq!(rotate(&fence, 90).block_state, state(&[("south", "true"), ("west", "true")]));
    }

    #[test]
    fn four_quarter_turns_are_identity() {
        let b = block("minecraft:oak_stairs", &[("facing", "south"), ("axis", "x"), ("rotation", "3"), ("north", "true"), ("east", "false")]);
        let mut r = b.clone();
        for _ in 0..4 {
            r = rotate(&r, 90);
        }
        assert_eq!(r, b);
    }

    #[test]
    fn relative_states_are_untouched() {
        let stair = block("minecraft:oak_stairs", &[("facing", "east"), ("shape", "inner_left"), ("half", "top")]);
        let r = rotate(&stair, 90);
        assert_eq!(r.block_state["shape"], "inner_left");
        assert_eq!(r.block_state["half"], "top");
        assert_eq!(r.block_state["facing"], "south");
    }

    #[test]
    fn block_nbt_is_preserved_through_rotation() {
        let mut sign = block("minecraft:oak_sign", &[("rotation", "0")]);
        let nbt = match crate::val::from_json(r#"{"front_text": {"messages": ["hi", "", "", ""], "has_glowing_text": true}}"#) {
            Val::Dict(d) => d,
            _ => unreachable!(),
        };
        sign.block_nbt = Some(nbt.clone());
        let r = rotate(&sign, 90);
        assert_eq!(r.block_state["rotation"], "4");
        assert_eq!(r.block_nbt, Some(nbt));
    }

    // Ported from tests/test_transform_execution.py.
    #[test]
    fn four_quarter_turns_return_points_and_facing_to_start() {
        let t = Transform { translation: Point::ZERO, rotation: Rotation::R90, source_size: Point::new(2, 1, 2) };
        let mut p = Point::ZERO;
        let mut b = block("minecraft:oak_stairs", &[("facing", "south")]);
        for _ in 0..4 {
            p = t.apply_point(p);
            b = b.transformed(&t);
        }
        assert_eq!(p, Point::ZERO);
        assert_eq!(b.block_state["facing"], "south");
    }

    #[test]
    fn apply_point_matches_python_formulas() {
        let size = Point::new(4, 2, 3);
        let p = Point::new(1, 1, 0);
        let at = |deg| Transform { translation: Point::new(10, 0, 20), rotation: Rotation::from_degrees(deg).unwrap(), source_size: size }.apply_point(p);
        assert_eq!(at(0), Point::new(11, 1, 20));
        assert_eq!(at(90), Point::new(10 + 3 - 1, 1, 21));
        assert_eq!(at(180), Point::new(10 + 4 - 1 - 1, 1, 20 + 3 - 1));
        assert_eq!(at(270), Point::new(10, 1, 20 + 4 - 1 - 1));
    }

    #[test]
    fn region_errors_and_display_match_python() {
        let err = Region::new(Point::new(1, 0, 0), Point::new(1, 1, 1)).unwrap_err();
        assert_eq!(err, "box must have positive extents: Box(min=Point(x=1, y=0, z=0), max=Point(x=1, y=1, z=1))");
        let d = Diagnostic::new("split_overflow", "too big", "Root/body").with_source(Some(SourceRef { file: "a.star".into(), line: Some(3), column: None }));
        assert_eq!(d.to_string(), "split_overflow: Root/body (a.star:3): too big");
        let e = BuildError::new(vec![Diagnostic::new("a", "m1", "p"), Diagnostic::new("b", "m2", "q")]);
        assert_eq!(e.to_string(), "a: p: m1\nb: q: m2");
    }
}
