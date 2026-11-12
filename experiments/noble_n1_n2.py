"""Noble round, part 1: clamp the slow variable; which settings can both relay and escape.

N1  Noble's voltage clamp on the clock (constant 1.0). The slow whole-unit variable is var,
    the variance of the last 50 signal_in values; it picks damp or amplify for the fast part.
    Clamp it, replay it, replay it shifted, and replay it into a unit whose fast state was
    scrambled (Sol's caveat: is the trace sufficient whatever the fast state is?).
N2  For constants 1.0..1.6: drive with 2-tick setpoint pulses every P ticks, then stop.
    Relay: fraction of pulses answered by exactly one beat 3..6 ticks later; extra beats.
    Escape: does the unit beat on its own after the input stops, and when.
    Also the window neuron (no slow state) as the control.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "experiments")]
import gn27 as g                       # noqa: E402
from window import WindowNet           # noqa: E402


class ClampNet(g.Net):
    """gn27.Net with one optional change: var can be overridden. clamp=None is gn27.Net exactly
    (tests/test_noble.py checks this tick for tick)."""
    clamp = None

    def step(self, ext=None, sp_ext=None):
        n = self.n
        src = self.pipe[0]
        live = ~np.isnan(src)
        q = g.q_of(np.where(live, src, 0.0))
        own = np.where(live, g.OWN[q - g.QMIN], 0.0)
        R = own if ext is None else own + ext
        self.hist[:, self.count % g.W] = R
        self.count += 1
        var = np.zeros(n)
        if self.count > 10:
            k = min(self.count, g.W)
            idx = (self.count - 1 - np.arange(k)) % g.W
            var = np.var(self.hist[:, idx], axis=1)
        if self.clamp is not None:
            var = np.full(n, float(self.clamp(self.t) if callable(self.clamp) else self.clamp))
        self.sent = np.roll(self.sent, 1, axis=0)
        self.sent[0] = np.where(live, g.WIRE[q - g.QMIN], 0.0)
        m = np.zeros(n)
        if self.wired and len(self._j):
            np.add.at(m, self._i, self._w * self.sent[self._L, self._j])
        mm = m if sp_ext is None else m + sp_ext
        S = 0.5 + 0.1 * (self.c + mm)
        hot = var > g.TARGET
        o = np.where(hot, S + (2 / (1 + np.exp(-3 * (R - S))) - 1) / 3,
                     S + np.tanh(2 * (R - S) * (1 + 10 * np.abs(var - g.TARGET))))
        self.pipe = np.vstack([self.pipe[1:], o[None, :]])
        self.S, self.var, self.q, self.m, self.own = S, var, q, m, own
        self.t += 1
        return own


def clock(clamp_at=300, T=900, clamp=None, scramble=None):
    net = ClampNet([g.CLOCK]); g.settle(net, 600)
    det, t0, trace = g.Beats(1), net.t, []
    for k in range(T):
        if k == clamp_at:
            net.clamp = clamp
            if scramble is not None:                 # replace the fast state, keep the slow one
                net.pipe = np.random.default_rng(scramble).uniform(0.3, 1.0, size=net.pipe.shape)
        det.see(net.step(), net.t)
        trace.append(float(net.var[0]))
    return [int(e - t0) for e in det.ev[0]], trace


def n1():
    free, tr = clock()
    t_base = 600                                     # net.t when the run starts (settle = 600)
    replay = lambda t, s=0: tr[(t - t_base - 1 + s) % len(tr)]   # noqa: E731
    out = {"free": free,
           "clamp_high_0.5": clock(clamp=0.5)[0],
           "clamp_low_0.0": clock(clamp=0.0)[0],
           "clamp_edge_0.1": clock(clamp=0.1)[0],
           "replay_own_trace": clock(clamp=replay)[0],
           "replay_shifted_20": clock(clamp=lambda t: replay(t, 20))[0]}
    for s in range(5):                               # fast state scrambled at the clamp moment
        out[f"replay_own_trace_fast_scrambled_{s}"] = clock(clamp=replay, scramble=s)[0]
        out[f"free_fast_scrambled_{s}"] = clock(clamp=None, scramble=s)[0]
    return out


def drive(make, P, T_on=600, T_off=400, w=-10.0):
    net = make()
    det, t0 = g.Beats(1), net.t
    pulses = list(range(40, T_on, P))
    for k in range(T_on + T_off):
        sp = np.array([w]) if any(0 <= k - p < 2 for p in pulses) else None
        det.see(net.step(sp_ext=sp), net.t)
    ev = [int(e - t0) for e in det.ev[0]]
    answered = sum(1 for p in pulses if sum(1 for e in ev if p + 3 <= e <= p + 6) == 1)
    extra_on = [e for e in ev if e < T_on + 6 and not any(p + 3 <= e <= p + 6 for p in pulses)]
    after = [e for e in ev if e >= pulses[-1] + 7]
    return {"answered": answered / len(pulses), "extra_beats_while_driven": len(extra_on),
            "first_beat_after_input_stops": (after[0] - pulses[-1]) if after else None,
            "beats_after_stop": len(after)}


def n2():
    res = {}
    for c in [1.0, 1.1, 1.2, 1.3, 1.35, 1.4, 1.45, 1.5, 1.6]:
        make = lambda c=c: g.settle(g.Net([c]), 1500)   # noqa: E731
        res[str(c)] = {str(P): drive(make, P) for P in (16, 32, 48, 70)}
    res["window"] = {str(P): drive(lambda: WindowNet([1.6]), P) for P in (16, 32, 48, 70)}
    return res


if __name__ == "__main__":
    r = {"N1_clamp": n1(), "N2_dual_role": n2()}
    for k, v in r["N1_clamp"].items():
        print(f"{k:38s} {v[:14]}")
    for c, d in r["N2_dual_role"].items():
        print(c, {P: (round(x['answered'], 2), x['extra_beats_while_driven'], x['first_beat_after_input_stops'], x['beats_after_stop']) for P, x in d.items()})
    out = ROOT / "results" / "noble.json"
    old = json.loads(out.read_text()) if out.exists() else {}
    old.update(r); out.write_text(json.dumps(old, indent=1))
