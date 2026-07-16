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
    uv run starlark-to-nbt build "$source" --output "$output"
done
