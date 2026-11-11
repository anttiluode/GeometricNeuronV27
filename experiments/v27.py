"""v27 (Fable 5.2, with Sol's cable proposal and Argon's two checks).

Everything here runs gn27.py: the original loop, plus edges that have a length.

  band        which edge weights let a one-way ring of silent relays keep a pattern
  memory      random bit patterns in rings of 1..16 units, 1,000 laps
  runs        how long a run of 1s can be (the 50-tick variance window, Argon's check)
  erase       signal_in 8-tick rhythm (Argon predicted it fails) vs the setpoint port
  loop        ONE unit and ONE cable of length L: 4 + L slots
  noise       Gaussian noise on setpoint_mod every tick
  distance    one sender, receivers at cable lengths 0..40, attenuation exp(-L / 10)
  regen       a ring whose edges get longer until the attenuated beat is not regenerated
  clock       a constant-1.0 unit (59-tick clock) writing into, and gating, a ring / a loop
  selfcable   two-way chains: does a unit's own beat, fed back on a 4-tick cable, stop runaway

Run: python experiments/v27.py      (about 6 minutes)      Writes: results/v27.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gn27 import CLOCK, RELAY, Beats, Net, pulse, read, ring_edges, rings, settle, write  # noqa: E402

S = lambda a: "".join(map(str, a))  # noqa: E731


def band():
    rng = np.random.default_rng(0)
    ws = np.round(np.arange(-4.5, -7.01, -0.05), 2)
    net, off = rings([(8, w, 0) for w in ws])
    bits = np.tile((rng.random(32) < 0.4).astype(int), (len(ws), 1))
    write(net, off, bits)
    first = read(net, off, 32)
    for _ in range(300):
        last = read(net, off, 32)
    good = [float(w) for w, a, b in zip(ws, first, last)
            if np.array_equal(np.roll(bits[0], 4), a) and np.array_equal(a, b)]
    res = {"ring": "8 relays, one 32-bit pattern with 11 ones, 300 laps", "weights_tried": [float(ws[0]), float(ws[-1]), 0.05],
           "weights_that_keep_it_exactly": good}
    print("band", good, flush=True)
    return res


def memory():
    rng = np.random.default_rng(1)
    res = {}
    for N in (1, 2, 4, 8, 16):
        lap, B = 4 * N, 40
        net, off = rings([(N, -6.0, 0)] * B)
        bits = (rng.random((B, lap)) < rng.choice([0.1, 0.3, 0.5, 0.8], size=(B, 1))).astype(int)
        write(net, off, bits)
        first = read(net, off, lap)
        for _ in range(1000):
            last = read(net, off, lap)
        res[f"{N} units, {lap} slots"] = {
            "patterns": B,
            "read_back_as_written_on_lap_1": int(sum(np.array_equal(np.roll(b, 4), a) for b, a in zip(bits, first))),
            "identical_after_1000_laps": int(sum(np.array_equal(a, b) for a, b in zip(first, last))),
            "failures_written_then_lap_1000": [[S(a), S(b)] for a, b in zip(first, last) if not np.array_equal(a, b)]}
        print("memory", N, res[f"{N} units, {lap} slots"], flush=True)
    return res


def runs():
    res = {}
    for r in (8, 30, 40, 45, 48, 49, 50, 52, 60, 64):
        net, off = rings([(16, -6.0, 0)])
        bits = np.zeros((1, 64), dtype=int)
        bits[0, :r] = 1
        write(net, off, bits)
        a = read(net, off, 64)
        for _ in range(500):
            b = read(net, off, 64)
        res[str(r)] = {"ones_after_500_laps": int(b.sum()), "unchanged": bool(np.array_equal(a, b))}
        print("runs", r, res[str(r)], flush=True)
    return res


def erase():
    rng = np.random.default_rng(2)
    res = {}

    def fresh(B=12):
        net, off = rings([(8, -6.0, 0)] * B)
        bits = (rng.random((B, 32)) < 0.4).astype(int)
        write(net, off, bits)
        return net, off, read(net, off, 32)

    for amp in (0.2, 0.5, 1.0, 2.0, 4.0):
        net, off, a = fresh()
        for _ in range(10):
            read(net, off, 32, ext=lambda k: np.full(net.n, amp * (1 if net.t % 8 < 4 else -1)))
        for _ in range(5):
            b = read(net, off, 32)
        res[f"signal_in 8-tick rhythm, amplitude {amp}, all units, 10 laps"] = {
            "bits_before": int(a.sum()), "bits_after": int(b.sum()),
            "rings_unchanged_of_12": int(sum(np.array_equal(x, y) for x, y in zip(a, b)))}
    for m in (3, 6, 12, -20, -40):
        net, off, a = fresh()

        def sp(k):
            v = np.zeros(net.n)
            v[off] = m
            return v
        read(net, off, 32, sp=sp)
        for _ in range(5):
            b = read(net, off, 32)
        res[f"setpoint_mod {m:+d} on one unit for one lap"] = {"bits_before": int(a.sum()), "bits_after": int(b.sum())}
    net, off, a = fresh()
    tgt = [int(np.flatnonzero(x)[0]) for x in a]

    def sp1(k):
        v = np.zeros(net.n)
        for r, t in enumerate(tgt):
            if k == (t - 4) % 32:
                v[off[r]] = 12
        return v
    read(net, off, 32, sp=sp1)
    for _ in range(5):
        b = read(net, off, 32)
    want = a.copy()
    for r, t in enumerate(tgt):
        want[r, t] = 0
    res["setpoint_mod +12 for ONE tick: exactly that one bit removed, rings of 12"] = int(
        sum(np.array_equal(x, y) for x, y in zip(want, b)))
    for k, v in res.items():
        print("erase", k, v, flush=True)
    return res


def loop():
    rng = np.random.default_rng(3)
    res = {}
    for L in (0, 4, 12, 28, 55, 124, 252):
        lap, B = 4 + L, 20
        net, off = rings([(1, -6.0, L)] * B)
        bits = (rng.random((B, lap)) < rng.choice([0.1, 0.3, 0.5], size=(B, 1))).astype(int)
        write(net, off, bits)
        a = read(net, off, lap)
        for _ in range(300):
            b = read(net, off, lap)
        res[f"cable length {L}, {lap} slots"] = {
            "patterns": B, "read_back_as_written": int(sum(np.array_equal(np.roll(x, 4), y) for x, y in zip(bits, a))),
            "identical_after_300_laps": int(sum(np.array_equal(x, y) for x, y in zip(a, b)))}
        print("loop", L, res[f"cable length {L}, {lap} slots"], flush=True)
    return res


def noise():
    rng = np.random.default_rng(4)
    ws = np.round(np.arange(-4.9, -6.61, -0.05), 2)
    res = {}
    for sig in (0.02, 0.05, 0.1, 0.2):
        B = 8
        specs = [(8, w, 0) for w in ws for _ in range(B)]
        net, off = rings(specs)
        bits = (rng.random((len(specs), 32)) < 0.4).astype(int)
        write(net, off, bits)
        a = read(net, off, 32)
        for _ in range(300):
            b = read(net, off, 32, sp=lambda k: rng.normal(0, sig, net.n))
        ok = [np.array_equal(x, y) for x, y in zip(a, b)]
        per = {str(float(w)): int(sum(ok[i * B:(i + 1) * B])) for i, w in enumerate(ws)}
        res[f"sigma {sig}"] = {"rings_of_8_unchanged_after_300_laps_by_weight": {k: v for k, v in per.items() if v},
                               "weights_with_all_8_unchanged": [float(k) for k, v in per.items() if v == B]}
        print("noise", sig, res[f"sigma {sig}"], flush=True)
    return res


def distance(lam=10.0):
    res = {}
    Ls = list(range(41))
    for w0 in (-6, -12, -24, -48, -96):
        n = 1 + len(Ls)
        net = settle(Net(np.full(n, RELAY), [(0, 1 + k, w0, L) for k, L in enumerate(Ls)], lam=lam))
        det = Beats(n)
        for k in range(120):
            det.see(net.step(sp_ext=pulse(n, 0, k, 5)), k)
        fired = [L for k, L in enumerate(Ls) if det.ev[1 + k]]
        res[f"sender weight {w0}"] = {"receivers_that_beat_at_cable_length": fired,
                                      "their_effective_weight": [round(w0 * float(np.exp(-L / lam)), 2) for L in fired]}
        print("distance", w0, fired, flush=True)
    return res


def regen(lam=20.0, w=-6.5):
    Ls = list(range(13))
    net, off = rings([(4, w, L) for L in Ls], lam=lam)
    for k in range(6):
        a = np.zeros(net.n)
        a[off] = -10.0 if k in (0, 1, 4) else 0.0
        net.step(sp_ext=a)
    det = Beats(net.n)
    for k in range(20000):
        det.see(net.step(), k)
    res = {}
    for L, o in zip(Ls, off):
        lap = 4 * (4 + L)
        got = sum(t > 20000 - 10 * lap for t in det.ev[o])
        res[f"edge length {L}"] = {"effective_weight": round(w * float(np.exp(-L / lam)), 2),
                                   "beats_at_one_unit_in_the_last_10_laps": int(got), "expected_if_kept": 20}
        print("regen", L, res[f"edge length {L}"], flush=True)
    return res


def clock():
    res = {}
    net = settle(Net([CLOCK]))
    det = Beats(1)
    for k in range(6000):
        det.see(net.step(), k)
    res["clock_intervals"] = sorted(int(x) for x in set(np.diff(det.ev[0])))
    for wc in (-4, -5, -6, -7, -8):
        N = 8
        net = settle(Net([RELAY] * N + [CLOCK], ring_edges(N, -6.0) + [(N, 0, wc, 0)]))
        occ = [int(read(net, np.array([0]), 32).sum()) for _ in range(400)]
        res[f"clock writes into an 8-ring, weight {wc}"] = {"bits_in_ring_after_laps_1_5_20_100_400": [occ[i] for i in (0, 4, 19, 99, 399)]}
    for name, N, L in (("8-ring, lap 32", 8, 0), ("one-unit loop, lap 59", 1, 55), ("one-unit loop, lap 118", 1, 114),
                       ("one-unit loop, lap 60", 1, 56), ("one-unit loop, lap 64", 1, 60)):
        lap = N * (4 + L)
        net = settle(Net([RELAY] * N + [CLOCK], ring_edges(N, -6.0, L) + [(N, 0, 6.0, 0)]))
        bits = np.ones((1, lap), dtype=int)
        bits[0, ::7] = 0
        write(net, np.array([0]), bits)
        occ = [int(read(net, np.array([0]), lap).sum()) for _ in range(600)]
        res[f"clock gates (weight +6) {name}"] = {"bits_written": int(bits.sum()),
                                                  "bits_after_laps_1_10_100_600": [occ[i] for i in (0, 9, 99, 599)]}
    for k, v in res.items():
        print("clock", k, v, flush=True)
    return res


def selfcable(N=9):
    def edges(g, Ls=4, ring=False):
        e = []
        for i in range(N if ring else N - 1):
            j = (i + 1) % N
            e += [(i, j, -6.0, 0), (j, i, -6.0, 0)]
        if g:
            e += [(i, i, g, Ls) for i in range(N)]
        return e

    res = {}
    for g in (0, 4, 6, 8, 12, 16, 24):
        net = settle(Net([RELAY] * N, edges(g)))
        det = Beats(N)
        for k in range(2000):
            det.see(net.step(sp_ext=pulse(N, 4, k, 10)), k)
        res[f"two-way chain of 9, middle unit excited once, self-cable weight {g}"] = [len(e) for e in det.ev]
    for Ls in (2, 3, 5, 6):
        net = settle(Net([RELAY] * N, edges(12, Ls)))
        det = Beats(N)
        for k in range(2000):
            det.see(net.step(sp_ext=pulse(N, 4, k, 10)), k)
        res[f"same, weight 12, self-cable length {Ls}"] = [len(e) for e in det.ev]
    for g in (0, 12):
        net = settle(Net([CLOCK] + [RELAY] * (N - 1), edges(g)))
        det = Beats(N)
        for k in range(5900):
            det.see(net.step(), k)
        res[f"clock at one end, 100 clock periods, self-cable weight {g}"] = [len(e) for e in det.ev]
    for k, v in res.items():
        print("selfcable", k, v, flush=True)
    return res


if __name__ == "__main__":
    out = {"band": band(), "memory": memory(), "runs": runs(), "erase": erase(), "loop": loop(), "noise": noise(),
           "distance": distance(), "regen": regen(), "clock": clock(), "selfcable": selfcable()}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "v27.json").write_text(json.dumps(out, indent=1))
    print("wrote results/v27.json")
