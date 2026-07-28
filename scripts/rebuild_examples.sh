#!/bin/sh

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

mkdir -p build

find examples -maxdepth 1 -type f -name '*.star' -print | sort |
while IFS= read -r source; do
    name=$(basename "$source" .star)
    output="build/$name.nbt"
    printf 'Building %s -> %s\n' "$source" "$output"
    # Make refresh semantics explicit: both generated siblings must come from
    # this invocation, never from an earlier successful build.
    rm -f "$output" "build/$name.meta.json"
    uv run starlark-to-nbt build "$source" --output "$output"
done
