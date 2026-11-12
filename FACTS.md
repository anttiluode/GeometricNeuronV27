# FACTS: read this before touching the geometric neuron

This file exists because the `setpoint_mod` port was frozen at 0.6 and forgotten for seven
rounds. It lists what the machine is and what has been measured, with where each fact comes
from. If you are an AI starting a session on this line of repos, read it first and add to it.

Marks: **[v27]** measured in this repo (`experiments/v27.py`, `results/v27.json`).
**[noble]** measured in this repo (`experiments/noble_n1_n2.py`, `experiments/noble_n3.py`, `results/noble.json`).
**[SL r*n*]** reported in round *n* of GeometricNeuronSurfaceListener and not re-run here.
**[code]** read from code.

## 1. The machine

One unit is the 2025 Perception Lab graph `ecg.json`, reduced:

```
q(t)   = int(5 + 50 * o(t - 4))        checkerboard square size; 4 ticks of pipeline delay
taps   = G[q]                          16 sampled pixels of the checkerboard (taps.json)
R(t)   = taps[0..3] summed + whatever is wired to signal_in
var    = variance of the last 50 values of R
S(t)   = 0.5 + 0.1 * (everything wired to setpoint_mod, summed)
o(t)   = S + (2 / (1 + exp(-3 (R - S))) - 1) / 3            if var > 0.1   ("damp")
       = S + tanh(2 (R - S) (1 + 10 |var - 0.1|))           otherwise      ("amplify")
```

A **beat** is the unit's own reading R going above 3. That happens when |q| is about 1 to 11.

## 2. Ports of the Homeostatic Coupler

| Port | State | Note |
|---|---|---|
| `signal_in` | live | carries the four splitter wires `out_0..out_3` in `ecg.json` |
| `setpoint_mod` | **live** | `ecg.json` wires a Constant Signal of 1.0 here, which is where the 0.6 setpoint comes from. Rounds 1 to 7 froze it. [SL r8] |
| `gain_mod` | dead | in `edge_of_chaos` mode the node computes `effective_gain` and then multiplies by `self.gain`. [SL r8, from `coupler.py`] |

The splitter has 16 outputs. `out_0 + out_1` are the two **beat wires**: near zero at rest and
about 2.0 during a beat. [SL r8], table below [v27].

Not checked by me: any other port or internal state of the archived node files. The node
files are in GeometricNeuronOriginReview, not here. Check them before claiming a port is dead.

## 3. What one unit does, by its Constant Signal

| Constant | Behaviour | Source |
|---|---|---|
| 1.0 (original) | beats by itself every 59 ticks: a clock | [v27] `clock.clock_intervals`; [SL r9] |
| **1.1** | **relays every 2-tick pulse (0 extra beats) while driven faster than ~59 ticks, and beats by itself 64 ticks after input stops, then every 59/60**: relay and watchdog in one unit | [noble] N2 |
| 1.35 | still a clock, about 58 ticks | [SL r9] |
| 1.40 | every second beat missed | [SL r9] |
| 1.45 | no large beats; damps 92% of the time | [SL r9, r10] |
| 1.6 | silent, always damping: a **relay** | [SL r10], used throughout [v27] |

- A 2-tick setpoint pulse makes a relay beat exactly 4 ticks later, at any moment, and it can
  be pulsed again 2 ticks later. [SL r10]
- A relay keeps nothing by itself once input stops. [SL r10]
- Sending the 8-tick rhythm into `signal_in` silences a **clock** (amplitude 0.1 to 0.2). [SL r2]
  It does **not** silence or erase relays driven through `setpoint_mod`. [v27] `erase`

## 4. Numbers worth knowing [v27]

- **The unit is four interleaved lanes.** Output at tick t depends on output at t − 4, so ticks
  t, t+1, t+2, t+3 are separate streams, tied together only by the shared variance.
- **A relay at rest is not still.** Its square size flickers between about 40 and 52 and its
  variance sits near 0.14, just above the 0.1 line.
- **Beat wires by square size:**

  | q | −10 | −8 | −6 | −5 | −4 | −1 | **0** | 1 | 3 | 5 | 6 | 8 | 10 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | `out_0 + out_1` | 1.76 | 2.00 | 1.91 | 1.88 | 2.00 | 2.00 | **0.00** | 2.00 | 1.95 | 1.85 | 1.82 | 2.00 | 1.76 |

- **Square size 0 is a blank board.** It sends nothing and reads nothing. This is the hole at
  wire weight −5.5 that round ten could not explain: at that weight the evoked square size
  lands on 0.
- **The wire is not flat across the beat.** It varies from 1.76 to 2.00 with square size, so a
  beat does not arrive at one fixed strength. This is why the ring is fragile to noise.
- **The clock's beat on the wires** is two ticks of 1.59 and 1.94, then two ticks of 0.56
  four ticks later.

- **Two levels** [noble]. `var` is a slow whole-unit variable that gates the fast pipeline. Hold it
  at 0.5 or 0.0 and the clock stops; hold it at exactly 0.1 and the unit oscillates every 8 ticks;
  play back its own recorded `var` and the 59-tick beats return, at times set by the recording even
  if the fast state is replaced by random values. Phase lives in `var`, not in the pipeline.
- **Beat traffic clamps `var` high.** Under pulses every 4 to 32 ticks (unarchived Opus run) a relay's `var` stays at 0.5 to
  2.2, so every relay/XOR/ring result used one level only. This is why the window neuron matched.
- **The native watchdog counts sub-beat activity.** Sub-threshold wire blips (−2.6 on the setpoint)
  can abort an escape and delay it from 63 to 141 ticks. A beat-counting timer would not. [noble] N3

## 5. Things that were believed and turned out wrong

| Belief | What happened |
|---|---|
| Idle overlap silences the surface colony (Sol, round 1) | it is the 8-tick ripple, through the drive [SL r2] |
| There is no way to make a unit beat through an input (Fable, rounds 1 to 7) | `setpoint_mod` does it [SL r8] |
| At constant 1.45 the unit never leaves damping (Fable, r9) | it damps 92% of the time [SL r10] |
| The 8-tick rhythm will erase a relay ring (Fable, v27 plan) | it does not; Argon predicted this [v27] |
| A relay "gets tired" under sustained activity (a NotebookLM summary, Nov 12) | under pulses every 4 to 32 ticks it answers every pulse for 600 ticks and never leaves damping; under a held push it becomes the 59-tick clock or stays silent. No fatigue [noble N2 for pulses every 16 to 70 ticks; every 4 to 12 ticks in an unarchived Opus run] |
| The −5.5 hole and the post-beat wake will break multi-beat patterns (Argon) | at a good weight they do not: 40 of 40 random patterns for 1,000 laps. The real limits are runs of 49 or more 1s, and noise [v27] |

## 6. Open

- Two-way wiring still runs away. A self-cable helps at one weight and one length only. [v27]
- Why a clock one tick off a loop's lap refills erased slots with 1s. [v27], not diagnosed
- Nothing here learns. Every weight, length and constant is set by hand.
- The slow level does real causal work (the clock lives in it), but the only function found for
  it so far is a timeout that an ordinary timer also does. A network-level slow state, set by many
  units and fed back to them (Sol's Z), is not built. [noble]
- Nothing has been tested on a task.
- Vector length 2,048 (Antti's note) is not modelled: `taps.json` is for 16 samples per row.
