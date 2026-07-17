# Pattern wall gallery: four panels, each a different formula for choosing a
# block from (x, y), separated by generated pilaster columns. Demonstrates
# index-driven material/geometry variation -- the technique behind every
# "procedural" effect in this DSL, since there is no random()/noise() builtin.

PANEL_WIDTH = 6
HEIGHT = 8


def PilasterColumn(height, material="minecraft:smooth_stone"):
    return component(
        name="PilasterColumn",
        props={"height": height, "material": material},
        min_size=[1, height, 1],
        body=fill_region([0, 0, 0], [1, height, 1], block(material)),
    )


def CheckerboardPanel(width, height, block_a="minecraft:white_concrete", block_b="minecraft:black_concrete"):
    """Parity of x + y picks the block: the simplest procedural formula."""
    return component(
        name="CheckerboardPanel",
        props={"width": width, "height": height, "block_a": block_a, "block_b": block_b},
        min_size=[width, height, 1],
        body=group([
            place_block([x, y, 0], block(block_a if (x + y) % 2 == 0 else block_b))
            for x in range(width)
            for y in range(height)
        ]),
    )


def GradientPanel(width, height, palette=[
        "minecraft:red_concrete", "minecraft:orange_concrete", "minecraft:yellow_concrete",
        "minecraft:lime_concrete", "minecraft:light_blue_concrete", "minecraft:blue_concrete",
        "minecraft:purple_concrete", "minecraft:magenta_concrete"]):
    """A horizontal band per row, indexed into a palette by height fraction."""
    bands = len(palette)
    return component(
        name="GradientPanel",
        props={"width": width, "height": height, "bands": bands},
        min_size=[width, height, 1],
        body=group([
            fill_region([0, y, 0], [width, y + 1, 1], block(palette[y * bands // height]))
            for y in range(height)
        ]),
    )


def StripePanel(width, height, block_a="minecraft:oak_planks", block_b="minecraft:spruce_planks", period=4):
    """Diagonal stripes: (x - y) modulo period splits each cell into two bands."""
    return component(
        name="StripePanel",
        props={"width": width, "height": height, "period": period},
        min_size=[width, height, 1],
        body=group([
            place_block([x, y, 0], block(block_a if (x - y) % period < period // 2 else block_b))
            for x in range(width)
            for y in range(height)
        ]),
    )


def WaveFriezePanel(width, base=3, amplitude=3, period=6,
                     material="minecraft:cobblestone", accent="minecraft:mossy_cobblestone"):
    """A solid base course topped by merlons whose height follows a
    triangular wave -- a formula-driven crenellation, instead of the plain
    x % 2 alternation used by lib/fortifications.star's BattlementWall."""
    parts = [fill_region([0, 0, 0], [width, base, 1], block(material))]
    for x in range(width):
        wave = amplitude - abs((x % period) - period // 2)
        if wave > 0:
            parts.append(fill_region([x, base, 0], [x + 1, base + wave, 1], block(accent)))
    return component(
        name="WaveFriezePanel",
        props={"width": width, "base": base, "amplitude": amplitude, "period": period},
        min_size=[width, base + amplitude, 1],
        body=group(parts),
    )


def build(panel_width=PANEL_WIDTH, height=HEIGHT):
    panels = [
        CheckerboardPanel(panel_width, height),
        GradientPanel(panel_width, height),
        StripePanel(panel_width, height),
        WaveFriezePanel(panel_width),
    ]
    sizes = []
    children = []
    for panel in panels:
        sizes.append(fixed(1))
        children.append(PilasterColumn(height))
        sizes.append(fixed(panel_width))
        children.append(panel)
    sizes.append(fixed(1))
    children.append(PilasterColumn(height))
    total_width = len(panels) * (panel_width + 1) + 1
    return component(
        name="ProceduralFacade",
        props={"panel_width": panel_width, "height": height},
        min_size=[total_width, height, 1],
        body=split(axis="x", sizes=sizes, children=children),
    )
