//! Sparse structure NBT, gzip, and the JSON side outputs (port of
//! `serialize.py` and `pipeline.write_build_outputs`).
//!
//! Only written voxels are listed. Untouched cells are absent, so pasting
//! leaves terrain alone, and file size scales with content. Carved cells
//! remain explicit `minecraft:air`. Block-entity nbt goes on the block
//! entry, never in the palette, which is keyed on type + state only. Gzip
//! uses mtime 0 and no filename, so identical builds are byte-identical.

use std::io::Write as _;
use std::path::Path;

use flate2::{Compression, GzBuilder};

use crate::blocks::BlockId;
use crate::debug;
use crate::execute::SparseVolume;
use crate::ir::Node;
use crate::json;
use crate::model::{BuildError, Point};
use crate::nbt::{self, Compound, Tag};
use crate::pipeline::BuildResult;
use crate::val::{Dict, Val};

pub const DATA_VERSION_1_21_7: i32 = 4438;

/// A palette key: air types first, then block type, then sorted state.
type PaletteKey = (bool, String, Vec<(String, String)>);

fn serialize_error(message: String) -> BuildError {
    crate::model::fail("serialize_error", message, "<root>")
}

fn output_error(path: &Path, err: std::io::Error) -> BuildError {
    crate::model::fail("output_error", format!("cannot write {}: {err}", path.display()), "<root>")
}

/// Python `_to_nbt`: bool→Byte, int→Int, float→Double, str→String,
/// dict→Compound, list→List typed by its first item (empty → String).
fn to_tag(value: &Val) -> Result<Tag, String> {
    Ok(match value {
        Val::Bool(b) => Tag::Byte(*b as i8),
        Val::Int(i) => Tag::Int(i32::try_from(*i).map_err(|_| format!("Int({i}) is out of range"))?),
        Val::Float(f) => Tag::Double(*f),
        Val::Str(s) => Tag::String(s.clone()),
        Val::Dict(d) => Tag::Compound(compound(d)?),
        Val::List(items) => {
            let tags = items.iter().map(to_tag).collect::<Result<Vec<_>, _>>()?;
            let element = tags.first().map_or(nbt::STRING, Tag::id);
            nbt::list(element, tags)?
        }
        // Schema validation rejects null anywhere in nbt.
        Val::Null => return Err("cannot serialize None as NBT".into()),
    })
}

fn compound(d: &Dict) -> Result<Compound, String> {
    d.iter().map(|(k, v)| Ok((k.clone(), to_tag(v)?))).collect()
}

fn entry(name: &str, tag: Tag) -> (String, Tag) {
    (name.to_owned(), tag)
}

fn rel(p: Point, origin: Point) -> [i32; 3] {
    let r = p - origin;
    [r.x, r.y, r.z]
}

/// The uncompressed structure NBT payload.
pub fn structure_nbt(volume: &SparseVolume, blocks: &crate::blocks::BlockTable) -> Result<Vec<u8>, BuildError> {
    let points = volume.sorted_points();
    // Palette: one entry per (type, sorted state), whatever the nbt. Air
    // types sort first, then by key, as Python's sorted() does.
    let mut keys: Vec<PaletteKey> = Vec::new();
    let mut key_of: Vec<Option<usize>> = vec![None; blocks.len()];
    let mut used: Vec<bool> = vec![false; blocks.len()];
    for p in &points {
        used[volume.voxels[p].block.0 as usize] = true;
    }
    for (i, is_used) in used.iter().enumerate() {
        if *is_used {
            let (t, state) = blocks.get(BlockId(i as u32)).key();
            keys.push((t != "minecraft:air", t, state));
        }
    }
    keys.sort();
    keys.dedup();
    for (i, is_used) in used.iter().enumerate() {
        if *is_used {
            let (t, state) = blocks.get(BlockId(i as u32)).key();
            key_of[i] = Some(keys.binary_search(&(t != "minecraft:air", t, state)).expect("key collected above"));
        }
    }
    let palette: Vec<Tag> = keys
        .iter()
        .map(|(_, t, state)| {
            let mut c = vec![entry("Name", Tag::String(t.clone()))];
            if !state.is_empty() {
                c.push(entry("Properties", Tag::Compound(state.iter().map(|(k, v)| (k.clone(), Tag::String(v.clone()))).collect())));
            }
            Tag::Compound(c)
        })
        .collect();

    let origin = volume.bounds.min;
    let mut block_entries = Vec::with_capacity(points.len());
    for p in &points {
        let id = volume.voxels[p].block;
        let state = key_of[id.0 as usize].expect("used block") as i32;
        let mut c = vec![entry("state", Tag::Int(state)), entry("pos", nbt::ints(&rel(*p, origin)))];
        if let Some(block_nbt) = blocks.get(id).block_nbt.as_ref().filter(|d| !d.is_empty()) {
            c.push(entry("nbt", Tag::Compound(compound(block_nbt).map_err(serialize_error)?)));
        }
        block_entries.push(Tag::Compound(c));
    }

    let mut entities: Vec<_> = volume.entities.iter().collect();
    entities.sort_by_key(|e| e.sequence);
    let mut entity_entries = Vec::with_capacity(entities.len());
    for e in entities {
        let r = rel(e.pos, origin);
        let pos = [f64::from(r[0]) + 0.5, f64::from(r[1]), f64::from(r[2]) + 0.5];
        let mut data = compound(e.entity.nbt.as_ref().unwrap_or(&Dict::new())).map_err(serialize_error)?;
        data.push(entry("id", Tag::String(e.entity.entity_type.clone())));
        data.push(entry("Pos", nbt::doubles(&pos)));
        data.push(entry("Rotation", nbt::floats(&[e.entity.yaw as f32, e.entity.pitch as f32])));
        entity_entries.push(Tag::Compound(vec![
            entry("pos", nbt::doubles(&pos)),
            entry("blockPos", nbt::ints(&r)),
            entry("nbt", Tag::Compound(data)),
        ]));
    }

    let size = volume.bounds.size();
    let root = vec![
        entry("DataVersion", Tag::Int(DATA_VERSION_1_21_7)),
        entry("size", nbt::ints(&[size.x, size.y, size.z])),
        entry("palette", Tag::List(nbt::List { element: nbt::COMPOUND, items: palette })),
        entry("blocks", Tag::List(nbt::List { element: nbt::COMPOUND, items: block_entries })),
        entry("entities", Tag::List(nbt::List { element: nbt::COMPOUND, items: entity_entries })),
    ];
    nbt::write_root(&root).map_err(serialize_error)
}

/// Level 6, not 9: on structure NBT, zlib's level 9 is ~20x slower and
/// produces *larger* output (moonspire: 205ms/159KB against 11ms/129KB).
pub const GZIP_LEVEL: u32 = 6;

/// Gzip as CPython's `GzipFile(filename="", mtime=0, compresslevel=6)`
/// does: no filename, mtime 0, OS byte 255. The output is byte-identical
/// when both sides link the same zlib.
pub fn gzip(payload: &[u8]) -> Vec<u8> {
    let mut encoder = GzBuilder::new().mtime(0).operating_system(255).write(Vec::new(), Compression::new(GZIP_LEVEL));
    encoder.write_all(payload).expect("writing to a Vec cannot fail");
    encoder.finish().expect("writing to a Vec cannot fail")
}

pub fn write_structure_nbt(volume: &SparseVolume, blocks: &crate::blocks::BlockTable, path: &Path) -> Result<(), BuildError> {
    let bytes = gzip(&structure_nbt(volume, blocks)?);
    std::fs::write(path, bytes).map_err(|e| output_error(path, e))
}

fn write_json(value: &Val, path: &Path) -> Result<(), BuildError> {
    std::fs::write(path, json::dumps(value)).map_err(|e| output_error(path, e))
}

pub fn metadata_val(result: &BuildResult) -> Val {
    let mut d = Dict::new();
    d.insert("ground_level".into(), Val::Int(result.metadata.ground_level.into()));
    d.insert("y_offset".into(), Val::Int(result.metadata.y_offset().into()));
    Val::Dict(d)
}

/// Python `execute.dense_to_dict`: every cell of the root box, y/z/x nested.
pub fn dense_val(volume: &SparseVolume, blocks: &crate::blocks::BlockTable) -> Val {
    let block_vals: Vec<Val> = (0..blocks.len()).map(|i| debug::block_to_val(blocks.get(BlockId(i as u32)))).collect();
    let b = volume.bounds;
    let layers = (b.min.y..b.max.y)
        .map(|y| {
            Val::List((b.min.z..b.max.z).map(|z| {
                Val::List((b.min.x..b.max.x).map(|x| block_vals[volume.block_at(Point::new(x, y, z)).0 as usize].clone()).collect())
            }).collect())
        })
        .collect();
    let mut d = Dict::new();
    d.insert("origin".into(), b.min.to_val());
    d.insert("size".into(), b.size().to_val());
    d.insert("order".into(), Val::Str("y,z,x".into()));
    d.insert("blocks".into(), Val::List(layers));
    Val::Dict(d)
}

/// Python `write_build_outputs`: the NBT, `<stem>.meta.json` beside it, and
/// with `debug_dir` the per-stage JSON. The resolved tree is only kept when
/// `finish_build` was asked for debug output.
pub fn write_build_outputs(node: &Node, result: &BuildResult, nbt_path: &Path, debug_dir: Option<&Path>) -> Result<(), BuildError> {
    write_structure_nbt(&result.volume, &result.blocks, nbt_path)?;
    write_json(&metadata_val(result), &nbt_path.with_extension("meta.json"))?;
    let Some(dir) = debug_dir else {
        return Ok(());
    };
    std::fs::create_dir_all(dir).map_err(|e| output_error(dir, e))?;
    write_json(&node.to_val(), &dir.join("component-ir.json"))?;
    let resolved = result.resolved.as_ref().expect("finish_build(debug = true) keeps the resolved tree");
    write_json(resolved, &dir.join("resolved.json"))?;
    write_json(&debug::operations_to_val(&result.operations, &result.blocks), &dir.join("operations.json"))?;
    write_json(&debug::entities_to_val(&result.volume.entities), &dir.join("entities.json"))?;
    write_json(&dense_val(&result.volume, &result.blocks), &dir.join("dense.json"))
}
