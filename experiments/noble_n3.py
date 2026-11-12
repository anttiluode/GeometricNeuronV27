"""Noble round, part 2 (N3): Sol's four situations. Can the network tell its own continuing
activity from evidence supplied by the world?

Units (all the unchanged gn27 unit, only the constant differs):
  0      world relay (1.6), driven by 2-tick setpoint pulses = the world's beats
  1..8   ring of relays (1.6), lap 32 ticks = 8 slots of 4 ticks, read at unit 1
  9      comparator (1.6): world and ring at -4.5 each = XOR. Its wire goes to ring unit 3
         at -6 (the one-wire self-writing ring of KultaaVaiKatinkultaaOpus) when learning is on
  10     ring watchdog (1.1): listens to ring unit 1 at -6
  11     world watchdog (1.1): listens to the world relay at -6
Constant 1.1 is the setting N2 found that relays every pulse and also escapes (beats on its
own about 64 ticks after its input stops).

Phases of 20 laps each:
  P1 world plays slots {0,3,5}; learning on
  P2 world silent; ring keeps going
  P3 world silent; ring stopped
  P4 world returns with a NEW pattern {1,6}; learning on
Two variants:
  hold      learning off in P2 and P3 (the ring keeps its content), ring erased at the start
            of P3 with +12 on unit 1 for one lap (README result 4)
  learning  learning on throughout; nothing is erased by hand
Controls: an ordinary software watchdog (fires 64 ticks after the last input, then every 59)
run on the same input streams; the window neuron has no slow state and cannot escape (N2).
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gn27 as g   # noqa: E402

LAP, PH = 32, 20
W_XOR, W_RING, W_DOG = -4.5, -6.0, -6.0
C_DOG = 1.1
A, B = [0, 3, 5], [1, 6]


def build(learning=True, dog_w=W_DOG):
    e = [(1 + k, 1 + (k + 1) % 8, W_RING, 0) for k in range(8)]
    e += [(0, 9, W_XOR, 0), (1, 9, W_XOR, 0)]
    e += [(1, 10, dog_w, 0), (0, 11, dog_w, 0)]
    if learning:
        e += [(9, 3, W_RING, 0)]
    c = [g.RELAY] * 10 + [C_DOG, C_DOG]
    return g.settle(g.Net(c, e))


def world_ticks():
    """Beat ticks the world asks for (a pulse 4 ticks before each)."""
    out = set()
    for lap in range(4 * PH):
        ph = lap // PH
        slots = A if ph == 0 else (B if ph == 3 else [])
        for s in slots:
            out.add(lap * LAP + 4 * s + 8)
    return out


def run(variant):
    net = build(learning=True)
    learn_edges = list(net.edges)
    hold_edges = [x for x in learn_edges if not (x[0] == 9 and x[1] == 3)]
    W = world_ticks()
    pulses = {b - 4 for b in W} | {b - 3 for b in W}
    det = g.Beats(net.n)
    t0 = net.t
    for t in range(4 * PH * LAP):
        lap, ph = t // LAP, t // LAP // PH
        if variant == "hold" and t == PH * LAP:
            net.set_edges(hold_edges)
        if t == 3 * PH * LAP:
            net.set_edges(learn_edges)
        sp = np.zeros(net.n)
        if t in pulses:
            sp[0] = -10.0
        if variant == "hold" and 2 * PH * LAP <= t < 2 * PH * LAP + LAP:
            sp[1] = 12.0                                # erase the ring at the start of P3
        det.see(net.step(sp_ext=sp), net.t)
    ev = [[int(e - t0) for e in d] for d in det.ev]
    return ev


def per_phase(ev):
    return [sum(1 for e in ev if p * PH * LAP <= e < (p + 1) * PH * LAP) for p in range(4)]


def per_lap(ev):
    out = [0] * (4 * PH)
    for e in ev:
        if e // LAP < len(out): out[e // LAP] += 1
    return out


def slots(ev, lap):
    return sorted({(e % LAP) // 4 for e in ev if e // LAP == lap})


def software_watchdog(inputs, T_first=63, T_period=59.5, end=4 * PH * LAP):
    """An ordinary timer: fires T_first ticks after the last input, then every T_period
    (59.5: the native escape alternates 60 and 59) until the next input."""
    out, ins = [], sorted(inputs)
    for k, x in enumerate(ins):
        nxt = ins[k + 1] if k + 1 < len(ins) else end
        f = x + T_first
        while f < nxt:
            out.append(int(round(f))); f += T_period
    return out


def report(variant, ev):
    world, ring, xor, dog_r, dog_w = ev[0], ev[1], ev[9], ev[10], ev[11]
    r = {
        "beats_per_phase": {"world": per_phase(world), "ring@1": per_phase(ring), "comparator": per_phase(xor),
                            "ring_watchdog": per_phase(dog_r), "world_watchdog": per_phase(dog_w)},
        "comparator_per_lap": per_lap(xor),
        "ring_per_lap": per_lap(ring),
        "ring_slots_end_of_phase": [slots(ring, (p + 1) * PH - 1) for p in range(4)],
        "world_slots_P4_last_lap": slots(world, 4 * PH - 1),
        "ring_watchdog_relays_ring_beats_P1": sum(1 for e in ring if e < PH * LAP and any(e + 3 <= d <= e + 6 for d in dog_r)) / max(1, sum(1 for e in ring if e < PH * LAP)),
        "world_watchdog_relays_world_beats_P1": sum(1 for e in world if e < PH * LAP and any(e + 3 <= d <= e + 6 for d in dog_w)) / max(1, sum(1 for e in world if e < PH * LAP)),
    }
    # escape beats = watchdog beats not within 3..6 ticks after an input beat
    esc_r = [d for d in dog_r if not any(d - 6 <= e <= d - 3 for e in ring)]
    esc_w = [d for d in dog_w if not any(d - 6 <= e <= d - 3 for e in world)]
    r["escape_beats_per_phase"] = {"ring_watchdog": per_phase(esc_r), "world_watchdog": per_phase(esc_w)}
    sw_r, sw_w = software_watchdog(ring), software_watchdog(world)
    r["software_watchdog_per_phase"] = {"ring": per_phase(sw_r), "world": per_phase(sw_w)}

    def match(a, b, tol=3):
        return sum(1 for x in a if any(abs(x - y) <= tol for y in b)), len(a), len(b)
    r["native_vs_software_escape_matches(tol 3)"] = {"ring": match(esc_r, sw_r), "world": match(esc_w, sw_w)}
    # P4 recovery: laps until the comparator is silent for the rest of the phase
    cl = per_lap(xor)
    ok = [lap for lap in range(3 * PH, 4 * PH) if all(cl[l] == 0 for l in range(lap, 4 * PH))]
    r["P4_laps_until_comparator_silent"] = (ok[0] - 3 * PH) if ok else None
    r["P4_ring_matches_world_last_lap"] = slots(ring, 4 * PH - 1) == slots(world, 4 * PH - 1)
    def lat(src, esc):
        out = []
        for d in esc:
            last = max([e for e in src if e < d], default=None)
            prev = max([x for x in esc if x < d], default=None)
            if last is not None and (prev is None or prev < last): out.append(d - last)
        return out
    r["escape_latency_after_last_input"] = {"ring_watchdog": lat(ring, esc_r), "world_watchdog": lat(world, esc_w)}
    return r


if __name__ == "__main__":
    res = {}
    for variant in ("hold", "learning"):
        ev = run(variant)
        res[variant] = rep = report(variant, ev)
        print(f"\n== {variant}")
        for k, v in rep.items():
            if k not in ("comparator_per_lap", "ring_per_lap"):
                print(f"  {k}: {v}")
        print("  comparator per lap:", rep["comparator_per_lap"])
        print("  ring per lap      :", rep["ring_per_lap"])
    out = ROOT / "results" / "noble.json"
    old = json.loads(out.read_text()) if out.exists() else {}
    old["N3_four_situations"] = res
    out.write_text(json.dumps(old, indent=1))
