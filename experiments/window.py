# Copied unchanged from anttiluode/KultaaVaiKatinkultaaOpus (the control neuron).
"""The control: an abstract window neuron with NO checkerboard, NO variance memory.

out(t+4) = beat  if  LO <= m(t) <= HI   else silence,   m(t) = c-free sum of w * wire_j(t) + sp_ext
A beat sends wire 2.0 on each beat tick. Band edges copied from E1 (GN27 relay, 2-tick pulse).
Same interface as gn27.Net so every experiment can swap it in.
"""
import numpy as np
LO, HI, D = -13.5, -8.4, 4

class WindowNet:
    def __init__(self, const, edges=(), lam=None, seed=None):
        self.n = n = len(np.atleast_1d(const))
        self.edges = [(int(j), int(i), float(w), int(L)) for j, i, w, L in edges]
        self.pipe = np.zeros((D, n), bool)      # beats scheduled D ticks ahead
        self.wire = np.zeros(n); self.t = 0; self.wired = True
        self.m = np.zeros(n); self.sent = np.zeros((1, n))
    def step(self, ext=None, sp_ext=None):
        fire = self.pipe[0].copy()
        self.wire = np.where(fire, 2.0, 0.0)
        self.sent = self.wire[None, :]
        m = np.zeros(self.n)
        if self.wired:
            for j, i, w, L in self.edges: m[i] += w * self.wire[j]
        if sp_ext is not None: m = m + sp_ext
        self.m = m
        self.pipe = np.vstack([self.pipe[1:], ((m >= LO) & (m <= HI))[None, :]])
        self.t += 1
        return np.where(fire, 4.0, 1.5)

def settle(net, ticks=0): return net
