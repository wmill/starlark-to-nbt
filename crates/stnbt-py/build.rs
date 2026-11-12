//! Bakes a fingerprint of everything that determines build output into the
//! extension, as `STNBT_BUILD_FINGERPRINT`.
//!
//! It covers every file under `crates/`, the workspace `Cargo.toml` and
//! `Cargo.lock`, and `src/starlark_to_nbt/prelude.star`. Output caches (the
//! minecraft-mcp-api starlark-service) combine it with their own hash of
//! `lib/` and the Python sources. FNV-1a keeps it stable across toolchains.

use std::fs;
use std::path::{Path, PathBuf};

fn collect(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else { return };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if path.file_name().is_some_and(|n| n != "target") {
                collect(&path, out);
            }
        } else {
            out.push(path);
        }
    }
}

fn main() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("set by cargo"));
    let root = manifest.join("../..").canonicalize().expect("workspace root exists");
    let mut files = Vec::new();
    collect(&root.join("crates"), &mut files);
    for extra in ["Cargo.toml", "Cargo.lock", "src/starlark_to_nbt/prelude.star"] {
        let path = root.join(extra);
        println!("cargo:rerun-if-changed={}", path.display());
        if path.is_file() {
            files.push(path);
        }
    }
    println!("cargo:rerun-if-changed={}", root.join("crates").display());
    files.sort();

    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    let mut feed = |bytes: &[u8]| {
        for b in bytes {
            hash ^= u64::from(*b);
            hash = hash.wrapping_mul(0x0100_0000_01b3);
        }
    };
    for file in &files {
        let rel = file.strip_prefix(&root).unwrap_or(file).to_string_lossy().replace('\\', "/");
        feed(rel.as_bytes());
        feed(&[0]);
        feed(&fs::read(file).unwrap_or_default());
        feed(&[0]);
    }
    println!("cargo:rustc-env=STNBT_BUILD_FINGERPRINT={hash:016x}");
}
