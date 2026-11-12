//! Core pipeline for starlark-to-nbt.
//!
//! This crate is being ported stage by stage from the Python implementation in
//! `src/starlark_to_nbt/`; see `docs/rust-core-plan.md` for the phase plan and
//! the parity rules each stage must satisfy.

pub mod blocks;
pub mod debug;
pub mod eval;
pub mod execute;
pub mod ir;
pub mod json;
pub mod layout;
pub mod lowering;
pub mod model;
pub mod nbt;
pub mod pipeline;
pub mod schema;
pub mod serialize;
pub mod support;
pub mod val;
pub mod validators;

/// Crate version, exposed so the CLI and the Python shim can report which core they run.
pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    #[test]
    fn version_is_set() {
        assert!(!super::version().is_empty());
    }
}
