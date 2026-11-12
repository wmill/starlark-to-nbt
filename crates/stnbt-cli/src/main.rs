//! Native CLI. Until Phase 6 of docs/rust-core-plan.md it only reports its
//! version; builds still go through the Python `starlark-to-nbt` entry point.

fn main() {
    match std::env::args().nth(1).as_deref() {
        Some("--version") | Some("-V") => println!("starlark-to-nbt {}", stnbt_core::version()),
        _ => {
            eprintln!("starlark-to-nbt (native) {}: builds are not implemented yet; use `uv run starlark-to-nbt`", stnbt_core::version());
            std::process::exit(2);
        }
    }
}
