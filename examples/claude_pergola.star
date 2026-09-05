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
        at([2, 1, 3], Pergola(7, 7, 4)),
        at([4, 1, 4], Bench(3)),
        at([5, 1, 6], Sign(["", "Designed by", "Claude ☺", ""], color="orange", glowing=True)),
        at([5, 0, 10], Path(3, 1)),
        at([1, 1, 10], FlowerBed(3, 3)),
        at([7, 1, 10], FlowerBed(3, 3)),
        at([4, 1, 11], LanternPost()),
        at([6, 1, 11], LanternPost()),
    ]
    return component(
        name="ClaudePergola",
        props={},
        min_size=[WIDTH, HEIGHT, LENGTH],
        metadata={"ground_level": 1},
        body=group(parts),
    )
