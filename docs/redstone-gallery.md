# Interactive redstone gallery (Java 1.21.7)

Build with `uv run starlark-to-nbt build examples/redstone_showcase.star --output build/redstone_showcase.nbt`.
The structure is 82×12×90; its sidecar declares `ground_level=3` and `y_offset=-3`.
Place with the usual block updates enabled and allow the circuits to settle.
This is a structural demonstration, not a saved simulation snapshot. Runtime
behavior has **not been verified in Minecraft**.

Enter from the north. Each 18×20 station has a north-facing instruction sign;
two-block aisles separate stations and a two-block perimeter surrounds them.
Blue is input A, green is B, orange is a momentary pulse. Output signs identify
lamps. Circuit pads are exposed: use the clear floor around them for access.

| Row, west to east | Instructions and expected result |
| --- | --- |
| NOT / OR / NOR / NAND | Toggle labeled A/B levers and compare the output with the truth tables below. |
| AND / XOR / XNOR / toggle memory | Test the remaining gates; press the memory button, release, then press again. Each rising edge should toggle the copper bulb and Q lamp. |
| Pulse extender / repeater clock / hopper clock / analog meter | Follow the timing and analog instructions below. |
| Bridge / door / sorter / lamp matrix | Follow the practical station instructions below. |

| A B | OR | NOR | NAND | AND | XOR | XNOR |
| --- | --- | --- | --- | --- | --- | --- |
| 0 0 | 0 | 1 | 1 | 0 | 0 | 1 |
| 0 1 | 1 | 0 | 1 | 0 | 1 | 0 |
| 1 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| 1 1 | 1 | 0 | 0 | 1 | 0 | 1 |

NOT maps 0→1 and 1→0. Allow propagation time after changing inputs; transient
logic glitches are not a failure of the steady-state truth table.

- **Pulse extender:** press the stone button once. The intended output duration
  is 16 **redstone ticks** (32 game ticks, nominally 1.6 seconds). The input must
  be shorter than 16 redstone ticks. This is a direct/delayed bulb toggle circuit,
  not a retriggerable timer: wait for both output and delayed input to turn off
  before another press (at least three seconds for the supplied button).
  Long or overlapping pulses can leave the bulb in the wrong state; reload the
  station to reset it before timing again.
- **Repeater clock:** with the center lever off, press the orange button to
  inject a pulse. The center lever is a **stage lock**, not pause/resume.
  Depending on when it locks, the circulating pulse can vanish or become a
  constant signal. Unlock and try a new pulse only after the ring is dark;
  if it remains constantly powered, reload the station and start again.
  Reach the center lever from the side of the five-block-wide pad.
- **Hopper clock:** watch both output lamps and the moving redstone block.
  Open either hopper from the side to change the total inventory (initially
  16 redstone). More items should make each half-cycle longer; leave at least
  one transferable item. The empty right hopper starts locked and the left
  piston starts extended. Do not put items into both hoppers while measuring
  a period; let the inventory redistribute first.
- **Analog meter:** take the 15 distinct items from SUPPLY and drop them on the gold
  plate. The 15 numbered lamps tap successive dust cells through isolated
  repeaters: stronger input should light a longer prefix, starting at 1.
  Weighted plates count entities, so merged item stacks do not necessarily
  increase the reading. Use the supplied distinct item types, one at a time, to test all 15 levels. Pick everything up to reset.
- **Bridge:** use the lever from the north/side. Cross east–west along the
  movable row over the trench. ON pushes three blocks south to complete the
  crossing; OFF pulls them back, leaving a three-block-wide gap. Fixed banks
  are at each end. Walk around the station's south side to bypass the gap.
- **Door:** approach the two-wide opening from either north or south. The side
  lever closes the two-high passage when on and retracts it when off. The bus
  passes overhead. The lower pistons depend on Java quasi-connectivity and
  updates from the upper pistons; verify both heights on every cycle.
- **Sorter:** take redstone and cobblestone from SUPPLY. Climb the side stairs
  to the balcony and insert both into the top INPUT barrel. The transport
  hoppers start empty. Redstone should reach the bottom FILTERED barrel;
  cobblestone should reach the elevated REJECT barrel at the south end.
  Leave the filter's 41 redstone and four filler panes untouched. Avoid inserting
  the filler item type; overflow safety does not make arbitrary filler inputs safe.
- **Matrix:** walk to the north/rear of the panel and use its 15 wall levers.
  Each lever powers one backing block and its corresponding lamp on the south
  face. Controls match world X and height; left/right appears reversed when
  viewing the opposite side. Walk around either end to inspect the front.

## Manual acceptance checklist

Run in Java 1.21.7 with normal block updates, without flight or placing wiring.
Record pass/fail and any transient behavior; these checks remain outstanding.

- [ ] Walk every aisle, reach all controls, and read instructions from the north.
- [ ] Verify every truth-table row, including NOT, then repeat in reverse order.
- [ ] Toggle memory at least ten times, waiting for button release each time.
- [ ] Measure the extender's 16-redstone-tick output; test repeated spaced pulses,
      then deliberately test a long pulse and an overlapping retrigger.
- [ ] Start the repeater clock; observe ten cycles. Lock during both on and off
      phases, unlock, and verify the documented restart/reset limitations.
- [ ] Observe ten hopper-clock reversals and both lamps. Change the item count
      to 1 and 32 and verify repeated cycling and a longer period for 32.
- [ ] Toggle bridge and door ten times. Check every piston, both door heights,
      clear travel, both approaches, the bridge crossing, and the bypass.
- [ ] Insert 32 redstone and 32 cobblestone into the sorter input; count 32 in
      each destination and verify that the filter remains 41+4 afterward.
- [ ] Test analog zero, low, middle, and full-strength readings; verify each
      numbered lamp threshold, no backwards illumination, and reset to zero.
- [ ] Toggle every matrix lever individually; only its pixel should change.
      Test all-on, all-off, and a checkerboard.

Automated checks cover geometry, allocation, support, diode states, inventories,
explicit air, and deterministic serialization. They do not execute redstone,
hopper transfers, piston updates, entity merging, or Minecraft placement updates.
