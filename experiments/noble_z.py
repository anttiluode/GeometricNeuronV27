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
probability p; at lap 50 ALL channels switch; at lap 90 ONE channel switches.
  world "big":   the switches go to unrelated patterns
  world "small": every switch adds or removes exactly ONE beat (weak evidence per channel, shared
                 across channels: where pooling should help most)
Score: over laps 20..129, the fraction of (channel, lap) in which the ring holds the world's clean
pattern (dropouts are not part of the pattern). Also laps to adapt after the two switches.

Conditions:
  always        gate always open (N3 'learning')
  hold          gate open for laps 0..19, then closed (N3 'hold')
  local Z       one Z per channel, from its own comparator
  shared Z      one Z for all four channels, from all comparators
  shared Z clamped   Z held at its own time-average from the free run
  shared Z replayed  the free run's Z trace, shifted 20 laps (right shape, wrong time)
  shared Z sets local thresholds   each channel's own Z decides, but its threshold is lo while
                the shared Z is above theta and hi otherwise (the shared state as a boundary condition
                on the local decision, Noble's sense of downward causation)
  GN variance, per channel / pooled   no added Z: a listening relay per channel hears its
                comparator at -6, and its own 50-tick variance (0.14 at rest, ~0.47 with one beat
                in the window, ~0.79 with two) is read as Z; pooled = sum of the four
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
        e += [(idx(c, 9), nc * U + c, W_RING, 0)]      # a listening relay per channel: its var is GN's own slow state
    return g.settle(g.Net([g.RELAY] * (nc * U + nc), e))


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


def neighbour(pat, rng):
    """A stable pattern with exactly one beat added or removed."""
    near = [q for q in stable_patterns() if len(set(q) ^ set(pat)) == 1]
    return near[rng.integers(len(near))][:]


def patterns_small(rng):
    pool = stable_patterns()
    first = [pool[rng.integers(len(pool))][:] for _ in range(C)]
    second = [neighbour(p, rng) for p in first]
    third = [p[:] for p in second]
    third[0] = neighbour(second[0], rng)
    return first, second, third


def schedule(seed, p=P_DROP, world="big"):
    rng = np.random.default_rng(seed)
    first, second, third = patterns(rng) if world == "big" else patterns_small(rng)
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


def run(seed, mode, theta=None, m=None, k=None, ztrace=None, p=P_DROP, world="big", lo=None, hi=None):
    clean, beats = schedule(seed, p, world)
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
        elif mode == "hier": gate = Zl > (lo if Zs > theta else hi)     # shared Z sets each channel's threshold
        elif mode == "gnvar_local": gate = net.var[C * U:C * U + C] > theta
        elif mode == "gnvar_shared": gate = np.full(C, net.var[C * U:C * U + C].sum() > theta)
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
    return best[0]           # includes world=..., so it can be passed straight to run()


def study(world, seeds=(1, 2, 3, 4, 5)):
    kw = {"world": world}
    th = {
        "local": tune("local", [{"theta": x, **kw} for x in (0.5, 1.5, 2.5, 3.5, 5.0, 7.0)]),
        "shared": tune("shared", [{"theta": x, **kw} for x in (1.5, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0)]),
        "software": tune("software", [{"m": m, "k": k, **kw} for k in (2, 3, 4) for m in range(2, k + 2)]),
        "gnvar_local": tune("gnvar_local", [{"theta": x, **kw} for x in (0.3, 0.4, 0.5, 0.6, 0.7, 0.9)]),
        "gnvar_shared": tune("gnvar_shared", [{"theta": x, **kw} for x in (0.7, 0.9, 1.1, 1.3, 1.6, 2.0, 2.5)]),
        "hier": tune("hier", [{"theta": t, "lo": a, "hi": b, **kw} for t in (3.5, 5.0, 7.0, 10.0)
                              for a in (0.5, 1.5) for b in (2.5, 3.5, 5.0)]),
    }
    print(world, "tuned on seed 0:", th, flush=True)
    res = {"tuned": th, "per_seed": {}}
    for sd in seeds:
        free = run(sd, "shared", **th["shared"])
        gfree = run(sd, "gnvar_shared", **th["gnvar_shared"])
        conds = {
            "always": run(sd, "always", **kw),
            "hold": run(sd, "hold", **kw),
            "local Z": run(sd, "local", **th["local"]),
            "shared Z": free,
            "shared Z clamped": run(sd, "clamped", theta=th["shared"]["theta"], ztrace=float(free["zs"].mean()), **kw),
            "shared Z replayed (+20 laps)": run(sd, "replayed", theta=th["shared"]["theta"], ztrace=free["zs"], **kw),
            "software counter": run(sd, "software", **th["software"]),
            "GN variance, per channel": run(sd, "gnvar_local", **th["gnvar_local"]),
            "GN variance, pooled": gfree,
            "shared Z sets local thresholds": run(sd, "hier", **th["hier"]),
        }
        res["per_seed"][sd] = {k: score(v) for k, v in conds.items()}
        print(world, sd, {k: round(v["correct"], 3) for k, v in res["per_seed"][sd].items()}, flush=True)
    mean = {}
    for name in res["per_seed"][seeds[0]]:
        vals = [res["per_seed"][s][name] for s in seeds]
        aa = [v["adapt_all_switch_laps"] for v in vals]
        ao = [v["adapt_one_switch_laps"] for v in vals]
        mean[name] = {"correct": round(float(np.mean([v["correct"] for v in vals])), 3),
                      "correct_before_switch": round(float(np.mean([v["correct_before_switch"] for v in vals])), 3),
                      "adapt_all_switch_laps": aa, "adapt_one_switch_laps": ao,
                      "adapt_all_mean_of_finite": round(float(np.mean([x for x in aa if x is not None])), 1) if any(x is not None for x in aa) else None,
                      "adapt_one_mean_of_finite": round(float(np.mean([x for x in ao if x is not None])), 1) if any(x is not None for x in ao) else None,
                      "writes": float(np.mean([v["writes"] for v in vals])),
                      "gate_open_frac": round(float(np.mean([v["gate_open_frac"] for v in vals])), 3)}
    res["mean"] = mean
    return res


if __name__ == "__main__":
    out = ROOT / "results" / "noble.json"
    old = json.loads(out.read_text()) if out.exists() else {}
    big = study("big")
    big["patterns_held_alone_without_dropouts"] = f"{len(stable_patterns())} of {len(candidates())}"
    big["p_drop"] = P_DROP
    small = study("small")
    small["p_drop"] = P_DROP
    old["Z_shared_slow_state"] = big
    old["Z_small_shared_changes"] = small
    out.write_text(json.dumps(old, indent=1))
    for name, r in (("BIG (all channels switch to unrelated patterns)", big), ("SMALL (every channel gains or loses one beat)", small)):
        print("\n" + name)
        for k, v in r["mean"].items():
            print(f"  {k:30s} correct {v['correct']:.3f}  before switch {v['correct_before_switch']:.3f}  adapt all {v['adapt_all_switch_laps']} one {v['adapt_one_switch_laps']}  writes {v['writes']:.0f}")
