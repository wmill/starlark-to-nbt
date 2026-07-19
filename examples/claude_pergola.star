# Garden nook: an open pergola sheltering a bench and a glowing standing sign
# that reads "Designed by Claude ☺", with a path and raised flower beds at the
# entrance. The grass pad occupies local Y=0, so ground level is 1.
#   uv run starlark-to-nbt build examples/claude_pergola.star \
#     --output build/claude_pergola.nbt --debug-dir build/claude_pergola

load("../lib/outdoor.star", "Pergola", "Path", "FlowerBed")
load("../lib/fixtures.star", "Sign", "Bench", "LanternPost")

WIDTH = 11
HEIGHT = 7
LENGTH = 13


def build():
    parts = [
        fill_region([0, 0, 0], [WIDTH, 1, LENGTH], block("minecraft:grass_block")),
        transform([2, 1, 3], 0, [7, 5, 7], Pergola(7, 7, 4)),
        transform([4, 1, 4], 0, [3, 1, 1], Bench(3)),
        transform([5, 1, 6], 0, [1, 1, 1],
                  Sign(["", "Designed by", "Claude ☺", ""], color="orange", glowing=True)),
        transform([5, 0, 10], 0, [1, 1, 3], Path(3, 1)),
        transform([1, 1, 10], 0, [3, 2, 3], FlowerBed(3, 3)),
        transform([7, 1, 10], 0, [3, 2, 3], FlowerBed(3, 3)),
        transform([4, 1, 11], 0, [1, 4, 1], LanternPost()),
        transform([6, 1, 11], 0, [1, 4, 1], LanternPost()),
    ]
    return component(
        name="ClaudePergola",
        props={},
        min_size=[WIDTH, HEIGHT, LENGTH],
        metadata={"ground_level": 1},
        body=group(parts),
    )
