//! Times the Rust pipeline stages on a dumped raw tree.
//!
//!     uv run python scripts/dump_tree.py examples/moonspire_magical_city.star /tmp/tree.json
//!     cargo run --release -p stnbt-core --example bench_stages -- /tmp/tree.json
//!
//! The JSON is `{"tree": ..., "root_size": [x, y, z]}`.

use std::time::Instant;

use stnbt_core::{execute, layout, lowering, model::{Point, Region}, schema, support, validators, val::Val};

fn convert(v: serde_json::Value) -> Val {
    match v {
        serde_json::Value::Null => Val::Null,
        serde_json::Value::Bool(b) => Val::Bool(b),
        serde_json::Value::Number(n) => n.as_i64().map_or_else(|| Val::Float(n.as_f64().unwrap()), Val::Int),
        serde_json::Value::String(s) => Val::Str(s),
        serde_json::Value::Array(a) => Val::List(a.into_iter().map(convert).collect()),
        serde_json::Value::Object(o) => Val::Dict(o.into_iter().map(|(k, v)| (k, convert(v))).collect()),
    }
}

fn main() {
    let path = std::env::args().nth(1).expect("usage: bench_stages <tree.json>");
    let mut doc: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let size: Vec<i32> = serde_json::from_value(doc["root_size"].take()).unwrap();
    let tree = convert(doc["tree"].take());
    let root = Region::from_size(Point::new(size[0], size[1], size[2]), Point::ZERO).unwrap();

    let t = Instant::now();
    let node = schema::parse_node(&tree, None).unwrap();
    let t_schema = t.elapsed();
    let t = Instant::now();
    let resolved = layout::resolve(&node, root).unwrap();
    let t_layout = t.elapsed();
    let t = Instant::now();
    let lowered = lowering::lower_all(&resolved).unwrap();
    let t_lower = t.elapsed();
    let writes: usize = lowered.operations.iter().map(|o| o.writes.len()).sum();
    let (ops, distinct) = (lowered.operations.len(), lowered.blocks.len());
    let t = Instant::now();
    let volume = execute::execute(&lowered.operations, root, lowered.entities.clone(), &lowered.blocks).unwrap();
    let t_execute = t.elapsed();
    let t = Instant::now();
    let metadata = match &node { stnbt_core::ir::Node::Component(c) => c.metadata.unwrap_or_default(), _ => Default::default() };
    let mut diags = support::support_diagnostics(&volume, root, metadata, &lowered.blocks);
    diags.extend(validators::validator_diagnostics(&lowered.validators, &lowered.operations, &volume, root, metadata, &lowered.blocks));
    let t_checks = t.elapsed();
    assert!(diags.is_empty(), "{diags:?}");
    println!(
        "schema {t_schema:?}  layout {t_layout:?}  lowering {t_lower:?}  execute {t_execute:?}  support+validators {t_checks:?}\n\
         ({ops} ops, {writes} writes, {} voxels, {distinct} distinct blocks)",
        volume.voxels.len()
    );
}
