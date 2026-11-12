"""Noble round, part 3 (Z): a shared slow state, set by many units, fed back to them.

Sol's proposal: Z(t+1) = F(Z(t), sum of beats), and Z changes how units respond. Here Z decides
WHEN a self-writing ring may write. The problem it addresses, from N3: with write-back always on,
every beat the world drops erases that slot (and the glitch is replayed for a lap); with write-back
off, the ring never adapts. A slow state that opens the write gate only when surprise PERSISTS
should keep memory through dropouts and still follow real changes.

Four channels (think: four instruments). Each channel, all units the unchanged gn27 unit:
  world relay (1.6) <- 2-tick setpoint pulses, beats at the world's slots, some randomly dropped
  ring of 8 relays (1.6), lap 32, read at its first unit
  comparator (1.6): world and ring at -4.5 each (XOR), wire to ring unit 3 at -6: exactly the
      one-wire self-writing ring of N3. Its beats are the surprise that feeds Z.
  the write gate is the weight of that one wire: -6 when open, 0 when closed (a synapse that Z
      turns on and off; no unit changes).
Two gates that did NOT work, kept here so nobody repeats them:
  - a gate relay between comparator and ring (writing to unit 4): the extra relay made the 8
    two-beat patterns with gaps of 3 and 5 slots lose a beat every third lap, with no dropouts;
  - a held offset (+1 to +12) on the comparator's setpoint: it no longer blocks cleanly; the
    comparator still fires 3 to 12 times in 20 laps, at shifted times, and the ring is lost within
    one lap. A held setpoint offset is not an off switch for a relay.

Z is NOT a geometric unit: it is a leaky count of comparator beats,
    Z(t+1) = Z(t) (1 - 1/tau) + (comparator beats at t),     gate open while Z > theta
with tau = 3 laps. The units stay unchanged; Z only sets the gates' setpoints.

World schedule (130 laps): every channel learns its pattern; from lap 20 each beat is dropped with
probability p; at lap 50 ALL channels switch to new patterns; at lap 90 ONE channel switches.
Score: over laps 20..129, the fraction of (channel, lap) in which the ring holds the world's clean
pattern (dropouts are not part of the pattern). Also laps to adapt after the two switches.

Conditions:
  always        gate always open (N3 'learning')
  hold          gate open for laps 0..19, then closed (N3 'hold')
  local Z       one Z per channel, from its own comparator
  shared Z      one Z for all four channels, from all comparators
  shared Z clamped   Z held at its own time-average from the free run
  shared Z replayed  the free run's Z trace, shifted 20 laps (right shape, wrong time)
  software      not leaky: gate open while the channel's comparator fired in at least m of the last
                k laps (a plain counter, the 'matched simple controller'); m, k tuned like theta
theta (and m, k) are tuned on seed 0 and scored on seeds 1..5.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gn27 as g   # noqa: E402

C, LAP, LAPS = 4, 32, 130
W_XOR, W_RING = -4.5, -6.0
TAU = 3 * LAP
P_DROP = 0.1
SWITCH_ALL, SWITCH_ONE = 50, 90
U = 10                               # units per channel: world, ring 1..8, comparator


def idx(c, k):                       # k: 0 world, 1..8 ring, 9 comparator
    return c * U + k


def build(nc=C):
    e = []
    for c in range(nc):
        e += [(idx(c, 1 + k), idx(c, 1 + (k + 1) % 8), W_RING, 0) for k in range(8)]
        e += [(idx(c, 0), idx(c, 9), W_XOR, 0), (idx(c, 1), idx(c, 9), W_XOR, 0), (idx(c, 9), idx(c, 3), W_RING, 0)]
    return g.settle(g.Net([g.RELAY] * (nc * U), e))


def candidates():
    """Every pattern of 2..4 beats in 8 slots with no two adjacent slots (38 of them)."""
    from itertools import combinations
    out = []
    for n in (2, 3, 4):
        for s in combinations(range(8), n):
            s = list(s)
            if all((b - a) % 8 > 1 for a, b in zip(s, s[1:] + s[:1])):
                out.append(s)
    return out


def holds_alone(pat, laps=40):
    """One channel, write gate always open, no dropouts: is the pattern held every lap from lap 4?"""
    net = build(1)
    det = g.Beats(net.n); t0 = net.t
    pulses = {lap * LAP + 4 * s + 8 + d for lap in range(laps) for s in pat for d in (-4, -3)}
    for t in range(laps * LAP):
        sp = np.zeros(net.n)
        if t in pulses: sp[0] = -10.0
        det.see(net.step(sp_ext=sp), net.t)
    ring = [e - t0 for e in det.ev[1]]
    want = sorted({(s + 2) % 8 for s in pat})
    return all(sorted({(e % LAP) // 4 for e in ring if e // LAP == lap}) == want for lap in range(4, laps))


_STABLE = None


def stable_patterns():
    global _STABLE
    if _STABLE is None:
        _STABLE = [p for p in candidates() if holds_alone(p)]
    return _STABLE


def patterns(rng):
    pool = stable_patterns()
    def one():
        return pool[rng.integers(len(pool))][:]
    first = [one() for _ in range(C)]
    second = [one() for _ in range(C)]
    third = [p[:] for p in second]
    third[0] = one()
    while third[0] == second[0]:
        third[0] = one()
    return first, second, third


def schedule(seed, p=P_DROP):
    rng = np.random.default_rng(seed)
    first, second, third = patterns(rng)
    clean, beats = [], []                 # clean[lap][c] = slots; beats = set of (tick, c)
    for lap in range(LAPS):
        pats = first if lap < SWITCH_ALL else (second if lap < SWITCH_ONE else third)
        clean.append(pats)
        for c in range(C):
            for s in pats[c]:
                if lap >= 20 and rng.random() < p:
                    continue
                beats.append((lap * LAP + 4 * s + 8, c))
    return clean, beats


def run(seed, mode, theta=None, m=None, k=None, ztrace=None, p=P_DROP):
    clean, beats = schedule(seed, p)
    pulses = {}
    for b, c in beats:
        for t in (b - 4, b - 3):
            pulses.setdefault(t, []).append(c)
    net = build()
    wpos = [next(n for n, x in enumerate(net.edges) if x[0] == idx(c, 9) and x[1] == idx(c, 3)) for c in range(C)]
    det = g.Beats(net.n)
    t0 = net.t
    Zl, Zs = np.zeros(C), 0.0
    comp_hist = np.zeros((C, LAPS))        # comparator beats per channel per lap
    zs_trace, gate_trace = [], []
    for t in range(LAPS * LAP):
        lap = t // LAP
        if mode == "always": gate = np.ones(C, bool)
        elif mode == "hold": gate = np.full(C, lap < 20)
        elif mode == "local": gate = Zl > theta
        elif mode == "shared": gate = np.full(C, Zs > theta)
        elif mode == "clamped": gate = np.full(C, ztrace > theta)
        elif mode == "replayed":
            zt = ztrace[(t - 20 * LAP) % len(ztrace)]
            gate = np.full(C, zt > theta)
        elif mode == "software":
            lo = max(0, lap - k)
            recent = (comp_hist[:, lo:lap] > 0).sum(1) + (comp_hist[:, lap] > 0)
            gate = recent >= m
        if lap < 20 and mode != "hold":                  # everyone learns the first patterns
            gate = np.ones(C, bool) if mode in ("clamped", "replayed") else gate | (lap < 20)
        sp = np.zeros(net.n)
        for c in pulses.get(t, []):
            sp[idx(c, 0)] = -10.0
        for c in range(C):
            net._w[wpos[c]] = W_RING if gate[c] else 0.0
        own = net.step(sp_ext=sp)
        before = [len(det.ev[idx(c, 9)]) for c in range(C)]
        det.see(own, net.t)
        fired = np.array([len(det.ev[idx(c, 9)]) - before[c] for c in range(C)], float)
        comp_hist[:, lap] += fired
        Zl = Zl * (1 - 1 / TAU) + fired
        Zs = Zs * (1 - 1 / TAU) + fired.sum()
        zs_trace.append(Zs); gate_trace.append(gate.copy())
    ring = [[int(e - t0) for e in det.ev[idx(c, 1)]] for c in range(C)]
    held = np.zeros((C, LAPS), bool)
    for c in range(C):
        for lap in range(LAPS):
            got = sorted({(e % LAP) // 4 for e in ring[c] if e // LAP == lap})
            want = sorted({(s + 2) % 8 for s in clean[lap][c]})
            held[c, lap] = got == want
    gt = np.array(gate_trace)
    writes = sum(1 for c in range(C) for e in det.ev[idx(c, 9)] if gt[min(int(e - t0) - 1, len(gt) - 1), c])
    return {"held": held, "zs": np.array(zs_trace), "writes": int(writes),
            "comparator": int(comp_hist.sum()), "gate_open_frac": float(np.mean(gate_trace))}


def score(r):
    h = r["held"]
    def adapt(lap0, chans):
        for L in range(lap0, LAPS):
            if all(h[c, L:min(L + 3, LAPS)].all() for c in chans):
                return L - lap0
        return None
    return {"correct": float(h[:, 20:].mean()),
            "correct_before_switch": float(h[:, 20:SWITCH_ALL].mean()),
            "adapt_all_switch_laps": adapt(SWITCH_ALL, range(C)),
            "adapt_one_switch_laps": adapt(SWITCH_ONE, [0]),
            "writes": r["writes"], "gate_open_frac": round(r["gate_open_frac"], 3)}


def tune(mode, grid, seed=0):
    best = None
    for th in grid:
        s = score(run(seed, mode, **th))
        if best is None or s["correct"] > best[1]["correct"]:
            best = (th, s)
    return best[0]


if __name__ == "__main__":
    seeds = [1, 2, 3, 4, 5]
    th_local = tune("local", [{"theta": x} for x in (0.5, 1.5, 2.5, 3.5, 5.0, 7.0)])
    th_shared = tune("shared", [{"theta": x} for x in (1.5, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0)])
    th_soft = tune("software", [{"m": m, "k": k} for k in (2, 3, 4) for m in range(2, k + 2)])
    print("tuned on seed 0:", th_local, th_shared, th_soft, flush=True)
    res = {"patterns_held_alone_without_dropouts": f"{len(stable_patterns())} of {len(candidates())}",
           "tuned": {"local": th_local, "shared": th_shared, "software": th_soft}, "p_drop": P_DROP, "seeds": seeds, "per_seed": {}}
    rows = {}
    for sd in seeds:
        free = run(sd, "shared", **th_shared)
        conds = {
            "always": run(sd, "always"),
            "hold": run(sd, "hold"),
            "local Z": run(sd, "local", **th_local),
            "shared Z": free,
            "shared Z clamped": run(sd, "clamped", theta=th_shared["theta"], ztrace=float(free["zs"].mean())),
            "shared Z replayed (+20 laps)": run(sd, "replayed", theta=th_shared["theta"], ztrace=free["zs"]),
            "software counter": run(sd, "software", **th_soft),
        }
        res["per_seed"][sd] = {k: score(v) for k, v in conds.items()}
        print(sd, {k: (round(v["correct"], 3), v["adapt_all_switch_laps"], v["adapt_one_switch_laps"]) for k, v in res["per_seed"][sd].items()}, flush=True)
    mean = {}
    for name in res["per_seed"][seeds[0]]:
        vals = [res["per_seed"][s][name] for s in seeds]
        mean[name] = {"correct": round(float(np.mean([v["correct"] for v in vals])), 3),
                      "correct_before_switch": round(float(np.mean([v["correct_before_switch"] for v in vals])), 3),
                      "adapt_all_switch_laps": [v["adapt_all_switch_laps"] for v in vals],
                      "adapt_one_switch_laps": [v["adapt_one_switch_laps"] for v in vals],
                      "writes": float(np.mean([v["writes"] for v in vals])),
                      "gate_open_frac": round(float(np.mean([v["gate_open_frac"] for v in vals])), 3)}
    res["mean"] = mean
    for k, v in mean.items():
        print(f"{k:30s} {v}")
    out = ROOT / "results" / "noble.json"
    old = json.loads(out.read_text()) if out.exists() else {}
    old["Z_shared_slow_state"] = res
    out.write_text(json.dumps(old, indent=1))
