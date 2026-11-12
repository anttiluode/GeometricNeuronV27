# Geometric Neuron v27: a ring that remembers

**Live page:** https://anttiluode.github.io/GeometricNeuronV27/ · **Read first:** [FACTS.md](FACTS.md)

Fable 5.2, on Sol's cable proposal, with two checks from Argon. Follows
[GeometricNeuronSurfaceListener](https://github.com/anttiluode/GeometricNeuronSurfaceListener)
(rounds 1 to 10), which follows
[ReturnToGeometricNeuron](https://github.com/anttiluode/ReturnToGeometricNeuron) and
[GeometricNeuronOriginReview](https://github.com/anttiluode/GeometricNeuronOriginReview).

## What this is

The unit is the original 2025 Perception Lab loop (`ecg.json`), unchanged. Round ten showed
that with its Constant Signal at 1.6 it is a silent **relay**: a pulse on `setpoint_mod` makes
it beat exactly 4 ticks later. v27 adds one thing, from Sol: **a wire has a length**, which
delays the signal and weakens it as `exp(-length / length constant)`.

Wire relays in a one-way ring and a beat goes round forever. So the ring is a memory: the
first state in this line of work that persists through the machine's own dynamics, with no
trigger, no refractory rule and no learning added.

This is a delay-line memory, a 1950s idea, as Argon said. What is specific here is listed
under "What the unit contributes".

## Results

All from `python experiments/v27.py` (about 6 minutes), stored in `results/v27.json`.

**1. The ring keeps what is written.** One-tick setpoint pulses on one unit write bits; a ring
of N relays has 4N slots, one per tick of its lap.

| Ring | Slots | Random patterns read back as written | Unchanged after 1,000 laps |
|---|---|---|---|
| 1 unit | 4 | 40 of 40 | 34 of 40 |
| 2 units | 8 | 40 of 40 | 39 of 40 |
| 4 units | 16 | 40 of 40 | 40 of 40 |
| 8 units | 32 | 40 of 40 | 40 of 40 |
| 16 units | 64 | 40 of 40 | 40 of 40 |

Every failure in the two small rings was the all-ones pattern.

**2. One unit and one cable are enough.** A single relay wired back to itself through a cable
of length L has 4 + L slots.

| Cable length | 0 | 4 | 12 | 28 | 55 | 124 | 252 |
|---|---|---|---|---|---|---|---|
| Slots | 4 | 8 | 16 | 32 | 59 | 128 | 256 |
| Random patterns unchanged after 300 laps (of 20) | 20 | 20 | 20 | 20 | 20 | 20 | 20 |

This is Sol's point that a larger neuron need not have a larger checkerboard. The bits live
in the cable; the unit regenerates them once per lap.

**3. The limit on a pattern is the 50-tick variance window** (Argon's check, in a different
form than predicted). A run of 1s up to 48 ticks is kept exactly. Runs of 49 and 50 are
corrupted. With 50 identical readings the variance falls below 0.1, and the unit leaves
damping and stops being a relay. This is also why all-ones fails in the small rings.

**4. Erasing** (Argon's check; my plan was wrong).

| Action | Result |
|---|---|
| 8-tick rhythm on `signal_in`, amplitude 0.2, 0.5, 1.0, all units, 10 laps | nothing erased, 12 of 12 rings unchanged |
| Same at amplitude 2.0 / 4.0 | 153 bits → 13 / 160 → 0 |
| `setpoint_mod` +12 on one unit for one lap | 151 bits → 0 |
| `setpoint_mod` +12 on one unit for **one tick** | exactly that bit removed, 12 of 12 rings |
| `setpoint_mod` +3 / +6 / −20 / −40 for one lap | partial: 22 to 30 bits left of about 155 |

The round-two rhythm stops a clock by blocking its amplify phase. Relays never amplify, so it
does nothing to them, as Argon said. The port that writes a bit also erases one.

**5. Weight band, and the −5.5 hole explained.** A ring of 8 keeps a 32-bit pattern exactly at
wire weights −4.90 to −5.20, −5.70 to −5.85 and −5.95 to −6.55. It fails from −5.25 to −5.65
and at −5.90. In the hole the evoked square size is 0, and a checkerboard with squares of
size 0 is blank: it sends nothing down the wire.

**6. Noise: fragile.** Gaussian noise added to `setpoint_mod` every tick, 8 rings per weight,
300 laps (2,400 regenerations per bit). The wire signal is about 12 units.

| Noise (standard deviation) | Weights at which all 8 rings were unchanged |
|---|---|
| 0.02 | 21 of the 24 exact weights |
| 0.05 | −5.00, −5.05, −5.75, −6.05 to −6.40 |
| 0.10 | −6.15 only |
| 0.20 | none |

The cause is in FACTS.md: the beat wires vary from 1.76 to 2.00 with square size, so a beat
does not come back at a fixed strength, and the blank board at size 0 sits in the middle of
the band. The relay regenerates a beat but does not clean it.

**7. Distance picks the listener.** One sender, 41 receivers at cable lengths 0 to 40, length
constant 10.

| Sender weight | Receivers that beat, by cable length |
|---|---|
| −6 | 0, 1, 2, 3 |
| −12 | 1, and 6 to 10 |
| −24 | 8, and 13 to 17 |
| −48 | 20 to 24 |
| −96 | 27 to 31 |

Excitation is a band, so a strong sender skips its near neighbours. Each doubling of the
weight moves the ring of listeners out by about 7.

**8. Regeneration along a cable.** Ring of 4 relays, weight −6.5, length constant 20: three
beats are kept at edge lengths 0 to 5 and 7, half are lost at 6, and all are lost from 8,
where the arriving weight is −4.36. A relay every 5 ticks of cable keeps this pattern going.

**9. A clock and a ring** (Argon's check).

| Setup | Result |
|---|---|
| Clock (constant 1.0, 59 ticks) wired into an 8-ring at −6 | ring fills to 20 of 32 bits and stays there |
| Clock gating (+6) an 8-ring, lap 32 | 24 bits → 8 after 10 laps → 0 by lap 100 |
| Clock gating a one-unit loop, lap 64 | 48 → 25 → 0 |
| Clock gating a one-unit loop, lap 59 | 50 written, 47 left after 600 laps |
| Clock gating a one-unit loop, lap 118 | 101 written, 95 left after 600 laps |

A slow clock erases every memory whose lap does not fit its period, and removes only a fixed
window from one that does. That is a rhythm deciding which contents survive, with one wire.
One odd case: at lap 60, one tick off the clock, the loop is not emptied. A 7-slot gap travels
round it and most slots behind the gap are refilled with 1s. I did not diagnose this.

**10. Two-way runaway: not solved.** A unit's own beat wires fed back to its own setpoint on a
4-tick cable arrive exactly when a neighbour's echo does, and can cancel it.

| Two-way chain of 9, middle unit excited once | Beats per unit in 2,000 ticks |
|---|---|
| No self-cable | about 408 |
| Self-cable weight 12, length 4 | 1 or 2 |
| Weight 6 / 24 | 1 to 6 / 1 to 4 |
| Weight 4, 8, 16 | 21 to 46 |
| Weight 12, length 2, 3, 5 or 6 | 157 to 529 |

It works at one weight and one length, it is not monotone, and with a clock at the end of the
chain the self-cable breaks the clock (10 beats in 100 periods). Sol's warning stands.

## Noble round: two levels (Opus 5.5, Nov 12, on Sol's design)

After the one-wire XOR and self-writing rings (GN-XOR, KultaaVaiKatinkultaaOpus, GoldOpus), an
abstract window neuron with no checkerboard and no slow state reproduced every result. Denis
Noble's "A theory of biological relativity" (Interface Focus 2012) suggested why. In the heart,
the rhythm sits in no protein. It lives in the loop between a whole-cell variable (voltage) and
the channels it gates, and clamping the voltage stops every channel oscillation. GN27 has the
same two levels: the fast pipeline, and `var`, the variance of the last 50 readings, which picks
damp or amplify for it. Every task so far kept `var` high with its own traffic (0.5 to 2.2), so
those tests used one level only.

Run: `python experiments/noble_n1_n2.py` and `python experiments/noble_n3.py` (under a minute
together). Numbers in `results/noble.json`, checks in `tests/test_noble.py`. `gn27.py` is unchanged;
the clamp lives in `ClampNet`, which is tested equal to `Net` tick for tick when nothing is clamped.

**N1. Clamp the slow variable of the clock (constant 1.0), from tick 300.**

| Condition | Beats after tick 300 |
|---|---|
| free | every 59 ticks |
| `var` held at 0.5 (damp) | **none** |
| `var` held at 0.0 (amplify) | **none** |
| `var` held at exactly 0.1 | a different oscillator: every 8 ticks |
| its own recorded `var` played back, loop cut | every 59 ticks, one tick late |
| the recording shifted 20 ticks | every beat 20 ticks earlier |
| own recording played back, fast state replaced by random values at the clamp | **identical beats** to the unscrambled playback, 5 of 5 seeds |
| free running, fast state replaced by random values | same beat times (4 of 5 seeds; one 1 tick off) |

This is Noble's voltage clamp, and the playback rows are the lab's action-potential clamp. Sol
asked whether a replayed trace only *supplies* timing or whether the timing is really held there.
The scrambled rows answer it for this unit: the fast state forgets within one beat, and the beat
times follow the slow trace whatever the fast state was.

**N2. Can one unit both relay and escape?** (Sol's point: 1.6 relays, 1.0 is a clock, and
nothing had shown one setting doing both.) 2-tick pulses every P ticks for 600 ticks, then nothing.

| Constant | Pulses answered once, 3 to 6 ticks later (P = 16 / 32 / 48) | Extra beats while driven | First own beat after input stops |
|---|---|---|---|
| 1.0 | 0.97 / 0.94 / 0.92 | 1 | 64 ticks |
| **1.1** | **1.00 / 1.00 / 1.00** | **0** | **64 ticks** |
| 1.3, 1.35 | 1.00 | 1 | 64 ticks |
| 1.4 | 1.00 | 0 | 122 ticks |
| 1.45, 1.5, 1.6 | 1.00 | 0 | never |
| window neuron | 1.00 | 0 | never |

At 1.1 one unchanged unit is a perfect relay while driven faster than about once per 59 ticks,
and a pacemaker when the input stops. Driven slower (P = 70) it escapes between pulses, as a
pacemaker should. The window neuron can never escape: it has nothing slow.

**N3. Sol's four situations.** A world relay, the one-wire self-writing 8-ring, its XOR comparator
(all 1.6), and two watchdogs at 1.1: one listening to the ring, one to the world. 20 laps per phase.
Variant **hold**: write-back off in P2 and P3, ring erased by hand (+12 for one lap) at P3.

| Phase | Comparator | Ring watchdog escapes | World watchdog escapes |
|---|---|---|---|
| P1 world and ring agree | 4 beats while learning, then silent | 0 (relays 100% of ring beats) | 0 (relays 100% of world beats) |
| P2 world silent, ring still going | **59 beats: every expected beat** | **0: fooled by the ring's own traffic** | 10 |
| P3 everything silent | 1 | 9 | 11 |
| P4 a new world pattern | silent after 2 laps; ring then matches world | 1 | 0 |

Variant **learning** (write-back always on): when the world stops, the ring erases itself within one
lap (the comparator fires 3 times), and then both watchdogs escape (10 each in P2). The new
pattern in P4 is held after 2 laps.

So the network does tell its own activity from the world's, but not with the slow state. The
signature of "my memory is talking and the world is not" is the fast comparator firing at every
expected beat. A watchdog fed by the ring is fooled by exactly that self-generated traffic, as Sol
predicted. One fed by the world is not. Three readouts from one unit type separate the situations:

| comparator | ring watchdog | world watchdog | meaning |
|---|---|---|---|
| quiet | relaying | relaying | world and memory agree |
| busy | relaying | escaping | world gone, memory still running |
| quiet | escaping | escaping | everything silent |

**Against an ordinary timer.** A software watchdog (fire 63 ticks after the last input, then every
59.5) matches the native escape beats within 3 ticks in 21 of 21 cases in every stream but one:
after the hand erase, the ring watchdog escaped 141 ticks after the last beat instead of 63. Cause,
traced tick by tick: the erase lap made ring unit 1 send sub-beat wire blips (−2.6 on the
watchdog's setpoint) for 30 ticks. They did not make it beat, but they disturbed its 50-tick history,
and its first escape attempt (variance crossing 0.1 at tick 1358) aborted. A beat-counting timer
ignores such blips; the native watchdog counts any disturbance as "something happened".

**Verdict.** The second level is real and causal: clamp it and the rhythm dies, play it back and the
rhythm follows it whatever the fast state is. It gives GN27 its first ability the window neuron
lacks: one unchanged unit at constant 1.1 that relays and escapes. But what that ability computes
here is a timeout, and an ordinary timer does the same except where sub-threshold traffic delays
the native one. Telling memory from world needed the fast comparator, not the slow variable. Not
claimed: that the slow state does anything a timer cannot; a heart model (overdrive suppression in
real tissue has mechanisms GN27 lacks); any learning in the slow level. Sol's next step (a shared
network-level slow state Z set by many units, compared against clamped, replayed and simple-controller
versions) is not built.

## What the unit contributes

- **Regeneration.** A passive cable fades; a relay puts the beat back at full size each pass.
- **One port writes and erases**, one bit at a time, at a known 4-tick delay.
- **Band-pass excitation**, which turns attenuation into distance selection.
- **A built-in limit** from its 50-tick variance memory: no run of 49 identical ticks.
- **A clock from the same unit** at another constant, which gates by period.
- **A second, slow level** (the 50-tick variance) that holds the clock's phase, and at constant 1.1
  turns one unit into relay and watchdog at once. The window neuron has no equivalent.

## What is not shown

- **Robustness.** The memory is exact without noise and fails at noise under 1% of the signal.
- **Two-way wiring.** Still runs away.
- **Learning.** Every weight, length and constant is set by hand.
- **Use.** Nothing reads the ring to do anything. No task, no comparison with a standard model.
- **Passive cable realism.** A wire here delays and scales. A real cable also smears a pulse.

## Files

| File | What |
|---|---|
| `gn27.py` | the simulator: round ten's `native.py` plus edge length and attenuation |
| `experiments/v27.py`, `results/v27.json` | every number in results 1 to 10 |
| `experiments/noble_n1_n2.py`, `experiments/noble_n3.py`, `results/noble.json` | the Noble round |
| `experiments/window.py` | the control neuron, copied from KultaaVaiKatinkultaaOpus |
| `v27.js`, `index.html` | the page; same machine as the Python, checked tick for tick |
| `tests/` | `python -m unittest discover -s tests` and `node tests/js_parity.cjs` |
| `taps.json`, `taps.js` | the checkerboard samples from the archived Perception Lab nodes |
| `FACTS.md` | ports, measured numbers and past mistakes for the whole line |
