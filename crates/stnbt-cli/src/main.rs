//! Native `starlark-to-nbt` CLI, equivalent to the Python `cli.py`:
//!
//!     starlark-to-nbt build SOURCE [--entry build] [--arg NAME=VALUE]... \
//!         --output OUT.nbt [--debug-dir DIR]
//!
//! It writes OUT.nbt and OUT.meta.json (plus the per-stage JSON with
//! `--debug-dir`). On a build error it prints the diagnostics to stderr and
//! exits 1; usage errors exit 2. `--arg` values become bools
//! (`true`/`false`, any case), then ints, then floats, else strings.

use std::path::PathBuf;
use std::process::ExitCode;

use clap::{Parser, Subcommand};
use stnbt_core::val::{Dict, Val};

#[derive(Parser)]
#[command(name = "starlark-to-nbt", version, about = "Build Minecraft structure NBT from Starlark")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Build a Starlark structure
    Build {
        source: PathBuf,
        #[arg(long, default_value = "build")]
        entry: String,
        #[arg(long = "arg", value_name = "NAME=VALUE", value_parser = parse_arg)]
        args: Vec<(String, Val)>,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        debug_dir: Option<PathBuf>,
    },
}

/// Python `cli._arg_value`.
fn arg_value(value: &str) -> Val {
    let lowered = value.to_lowercase();
    if lowered == "true" || lowered == "false" {
        return Val::Bool(lowered == "true");
    }
    let trimmed = value.trim();
    if let Ok(i) = trimmed.parse::<i64>() {
        return Val::Int(i);
    }
    if let Ok(f) = trimmed.parse::<f64>() {
        return Val::Float(f);
    }
    Val::Str(value.to_owned())
}

fn parse_arg(raw: &str) -> Result<(String, Val), String> {
    match raw.split_once('=') {
        Some((name, value)) => Ok((name.to_owned(), arg_value(value))),
        None => Err(format!("invalid --arg {raw:?}; expected NAME=VALUE")),
    }
}

fn main() -> ExitCode {
    let Command::Build { source, entry, args, output, debug_dir } = Cli::parse().command;
    let props: Dict = args.into_iter().collect();
    let run = || -> Result<(), stnbt_core::model::BuildError> {
        let tree = stnbt_core::eval::evaluate_file(&source, &entry, &props)?;
        let node = stnbt_core::schema::parse_node(&tree, Some(&source.to_string_lossy()))?;
        let result = stnbt_core::pipeline::build(&node, &props, None)?;
        stnbt_core::serialize::write_build_outputs(&node, &result, &output, debug_dir.as_deref())
    };
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::from(1)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arg_values_coerce_like_the_python_cli() {
        assert_eq!(arg_value("TRUE"), Val::Bool(true));
        assert!(matches!(arg_value("11"), Val::Int(11)));
        assert!(matches!(arg_value("-3"), Val::Int(-3)));
        assert!(matches!(arg_value("2.5"), Val::Float(f) if f == 2.5));
        assert!(matches!(arg_value("GableRoof"), Val::Str(s) if s == "GableRoof"));
        assert!(parse_arg("noequals").is_err());
        assert_eq!(parse_arg("name=a=b").unwrap().1, Val::Str("a=b".into()));
    }
}
