"""Geometric Neuron v27: the original ecg.json loop, on a graph whose edges have length.

One unit is the reduced Perception Lab loop, unchanged from GeometricNeuronSurfaceListener
(native.py, rounds 8-10), which was checked bit-exact against the archived nodes:

    q_i(t)   = int(5 + 50 * o_i(t - 4))            checkerboard square size, 4 ticks of pipeline
    taps     = G[q]                                the 16 splitter outputs
    R_i(t)   = taps[0] + taps[1] + taps[2] + taps[3] + ext_i(t)       signal_in
    var_i    = variance of the last 50 values of R_i
    S_i(t)   = 0.5 + 0.1 * (c_i + m_i(t) + sp_ext_i(t))               setpoint_mod
    o_i(t)   = damp around S_i if var_i > 0.1, else amplify around S_i

c_i is the Constant Signal node (1.0 in ecg.json; 1.6 makes a silent relay, round ten).

The ONLY thing v27 adds is on the edges (Sol's proposal). An edge j -> i has a weight w, a
length L (whole ticks of delay) and the network has one length constant lam:

    m_i(t) = sum over edges j->i of  w * exp(-L / lam) * (taps_j[0] + taps_j[1])(t - L)

taps[0] + taps[1] are the two "beat wires": loud only around a beat. L = 0 and lam = None
is native.py exactly (tests/test_gn27.py checks this against a stored fixture).
A negative w excites (it dips the setpoint); a positive w blocks an excitation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

_D = json.loads((Path(__file__).resolve().parent / "taps.json").read_text())
QMIN, QMAX = _D["qmin"], _D["qmax"]
G = np.array(_D["taps"], dtype=np.float64)
OWN = G[:, 0:4].sum(axis=1)            # what a unit hears of itself on signal_in
WIRE = G[:, 0] + G[:, 1]               # what it sends down an edge
TARGET, W, D = 0.1, 50, 4
O0 = 0.8739509815096245                # output saved in ecg.json
RELAY, CLOCK = 1.6, 1.0


def q_of(o):
    o = np.where(o == 0, 0.1, o)
    return np.clip(np.trunc(5 + 50 * o).astype(int), QMIN, QMAX)


class Net:
    def __init__(self, const, edges=(), lam=None, seed=None):
        self.c = np.atleast_1d(np.array(const, dtype=float))
        n = self.n = len(self.c)
        self.lam = lam
        self.set_edges(edges)
        self.maxL = max(self.maxL, 1)
        self.sent = np.zeros((self.maxL, n))           # sent[k] = beat wires k ticks ago
        self.hist = np.zeros((n, W))
        self.count = 0
        self.pipe = np.full((D, n), np.nan)
        self.pipe[-1] = O0
        if seed is not None:
            rng = np.random.default_rng(seed)
            self.pipe = rng.uniform(0.3, 1.0, size=(D, n))
            self.hist = rng.uniform(0.0, 1.6, size=(n, W))
            self.count = W
        self.t = 0
        self.wired = True                              # False: edges carry nothing (for settling)
        self.S = np.full(n, 0.6)
        self.var = np.zeros(n)
        self.q = np.zeros(n, dtype=int)
        self.m = np.zeros(n)

    def set_edges(self, edges):
        """Edges are (source j, target i, weight w, length L). Lengths cannot grow after init."""
        self.edges = [(int(j), int(i), float(w), int(L)) for j, i, w, L in edges]
        e = self.edges
        self._j = np.array([x[0] for x in e], dtype=int)
        self._i = np.array([x[1] for x in e], dtype=int)
        self._L = np.array([x[3] for x in e], dtype=int)
        self._w = np.array([x[2] * self.gain(x[3]) for x in e], dtype=float)
        self.maxL = max(getattr(self, "maxL", 0), max([x[3] for x in e], default=0) + 1)

    def gain(self, L):
        return 1.0 if self.lam is None else float(np.exp(-L / self.lam))

    def step(self, ext=None, sp_ext=None):
        n = self.n
        src = self.pipe[0]
        live = ~np.isnan(src)
        q = q_of(np.where(live, src, 0.0))
        own = np.where(live, OWN[q - QMIN], 0.0)
        R = own if ext is None else own + ext
        self.hist[:, self.count % W] = R
        self.count += 1
        var = np.zeros(n)
        if self.count > 10:
            k = min(self.count, W)
            idx = (self.count - 1 - np.arange(k)) % W
            var = np.var(self.hist[:, idx], axis=1)
        self.sent = np.roll(self.sent, 1, axis=0)
        self.sent[0] = np.where(live, WIRE[q - QMIN], 0.0)
        m = np.zeros(n)
        if self.wired and len(self._j):
            np.add.at(m, self._i, self._w * self.sent[self._L, self._j])
        mm = m if sp_ext is None else m + sp_ext
        S = 0.5 + 0.1 * (self.c + mm)
        hot = var > TARGET
        o = np.where(hot, S + (2 / (1 + np.exp(-3 * (R - S))) - 1) / 3,
                     S + np.tanh(2 * (R - S) * (1 + 10 * np.abs(var - TARGET))))
        self.pipe = np.vstack([self.pipe[1:], o[None, :]])
        self.S, self.var, self.q, self.m, self.own = S, var, q, m, own
        self.t += 1
        return own


class Beats:
    """Beat detector: a beat is the first tick a unit's own reading goes above 3."""

    def __init__(self, n):
        self.prev = np.ones(n, bool)
        self.ev = [[] for _ in range(n)]

    def see(self, own, t):
        loud = own > 3
        for u in np.flatnonzero(loud & ~self.prev):
            self.ev[u].append(t)
        self.prev = loud


def ring_edges(n, w=-6.0, L=0):
    return [(i, (i + 1) % n, w, L) for i in range(n)]


def run(net, ticks, ext=None, sp_ext=None, det=None):
    """ext / sp_ext: callables k -> array or None, k counted from 0 for this call."""
    det = det or Beats(net.n)
    for k in range(ticks):
        det.see(net.step(ext(k) if ext else None, sp_ext(k) if sp_ext else None), net.t)
    return det


def pulse(n, unit, k, at, m=-10.0, width=2):
    """Setpoint pulse on one unit for `width` ticks starting at tick `at` (the Excite button)."""
    a = np.zeros(n)
    if at <= k < at + width:
        a[unit] = m
    return a


# ---- helpers used by the experiments, the tests and the page fixture -------------------------

def settle(net, ticks=1500):
    """Let every unit idle with the edges silent, so no start-up transient is trapped in a loop."""
    net.wired = False
    for _ in range(ticks):
        net.step()
    net.wired = True
    return net


def rings(specs, lam=None, const=RELAY, extra=()):
    """Disjoint one-way rings in one net. specs = [(N, weight, edge length), ...].
    Returns the settled net and the index of the first unit of each ring."""
    edges, off, n = [], [], 0
    for N, w, L in specs:
        off.append(n)
        edges += [(n + i, n + (i + 1) % N, w, L) for i in range(N)]
        n += N
    return settle(Net(np.full(n, const), edges + list(extra), lam=lam)), np.array(off)


def write(net, off, bits, m=-10.0):
    """bits[ring, tick]: a one-tick setpoint pulse of size m on the ring's first unit per 1."""
    for k in range(bits.shape[1]):
        a = np.zeros(net.n)
        a[off] = m * bits[:, k]
        net.step(sp_ext=a)


def read(net, off, lap, ext=None, sp=None):
    """One lap of each ring as bits: 1 where the first unit's own reading is above 3."""
    out = np.zeros((len(off), lap), dtype=int)
    for k in range(lap):
        out[:, k] = net.step(ext(k) if ext else None, sp(k) if sp else None)[off] > 3
    return out
