#!/bin/sh
# Like rebuild_examples.sh, but with the native Rust binary (crates/stnbt-cli)
# instead of the Python entry point.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

cargo build --release -q -p stnbt-cli
binary="$repo_root/target/release/starlark-to-nbt"
mkdir -p build

find examples -maxdepth 1 -type f -name '*.star' -print | sort |
while IFS= read -r source; do
    name=$(basename "$source" .star)
    output="build/$name.nbt"
    printf 'Building %s -> %s\n' "$source" "$output"
    # Both generated siblings must come from this invocation.
    rm -f "$output" "build/$name.meta.json"
    "$binary" build "$source" --output "$output"
done
