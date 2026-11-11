// Geometric Neuron v27 in the browser: the same machine as gn27.py, tick for tick
// (tests/js_parity.cjs checks it against tests/fixture.json, which gn27.py wrote).
(function (root) {
  const T = root.GEOMETRIC_TAPS || (typeof require !== "undefined" ? (require("./taps.js"), globalThis.GEOMETRIC_TAPS) : null);
  const QMIN = T.qmin, QMAX = T.qmax, G = T.taps;
  const OWN = G.map(r => r[0] + r[1] + r[2] + r[3]);
  const WIRE = G.map(r => r[0] + r[1]);
  const TARGET = 0.1, W = 50, D = 4, O0 = 0.8739509815096245, RELAY = 1.6, CLOCK = 1.0;

  function qOf(o) {
    if (o === 0) o = 0.1;
    const q = Math.trunc(5 + 50 * o);
    return Math.max(QMIN, Math.min(QMAX, q));
  }

  class Net {
    // edges: [source, target, weight, length]; lam: length constant or null
    constructor(consts, edges, lam) {
      this.c = Float64Array.from(consts);
      const n = this.n = this.c.length;
      this.lam = lam == null ? null : lam;
      this.setEdges(edges || []);
      this.sent = Array.from({ length: this.maxL }, () => new Float64Array(n));
      this.head = 0;
      this.hist = Array.from({ length: n }, () => new Float64Array(W));
      this.count = 0;
      this.pipe = Array.from({ length: D }, (_, k) => new Float64Array(n).fill(k === D - 1 ? O0 : NaN));
      this.t = 0; this.wired = true;
      this.S = new Float64Array(n).fill(0.6); this.v = new Float64Array(n);
      this.q = new Int32Array(n); this.m = new Float64Array(n); this.own = new Float64Array(n);
    }
    gain(L) { return this.lam == null ? 1 : Math.exp(-L / this.lam); }
    setEdges(edges) {
      this.edges = edges.map(e => [e[0] | 0, e[1] | 0, +e[2], e[3] | 0]);
      this.ew = this.edges.map(e => e[2] * this.gain(e[3]));
      this.maxL = Math.max(this.maxL || 1, 1 + this.edges.reduce((a, e) => Math.max(a, e[3]), 0));
    }
    setWeights(fn) { this.edges.forEach((e, k) => { e[2] = fn(e, k); this.ew[k] = e[2] * this.gain(e[3]); }); }
    step(ext, sp) {
      const n = this.n, src = this.pipe[0];
      this.head = (this.head + this.maxL - 1) % this.maxL;
      const now = this.sent[this.head];
      const k = Math.min(this.count + 1, W);
      for (let i = 0; i < n; i++) {
        const live = !Number.isNaN(src[i]);
        const q = qOf(live ? src[i] : 0);
        this.q[i] = q;
        this.own[i] = live ? OWN[q - QMIN] : 0;
        now[i] = live ? WIRE[q - QMIN] : 0;
        const R = this.own[i] + (ext ? ext[i] : 0);
        this.hist[i][this.count % W] = R;
      }
      this.count++;
      this.m.fill(0);
      if (this.wired) for (let e = 0; e < this.edges.length; e++) {
        const ed = this.edges[e];
        this.m[ed[1]] += this.ew[e] * this.sent[(this.head + ed[3]) % this.maxL][ed[0]];
      }
      const o = new Float64Array(n);
      for (let i = 0; i < n; i++) {
        let v = 0;
        if (this.count > 10) {
          const h = this.hist[i];
          let mean = 0;
          for (let a = 0; a < k; a++) mean += h[(this.count - 1 - a) % W];
          mean /= k;
          for (let a = 0; a < k; a++) { const d = h[(this.count - 1 - a) % W] - mean; v += d * d; }
          v /= k;
        }
        const R = this.hist[i][(this.count - 1) % W];
        const S = 0.5 + 0.1 * (this.c[i] + this.m[i] + (sp ? sp[i] : 0));
        o[i] = v > TARGET ? S + (2 / (1 + Math.exp(-3 * (R - S))) - 1) / 3
          : S + Math.tanh(2 * (R - S) * (1 + 10 * Math.abs(v - TARGET)));
        this.S[i] = S; this.v[i] = v;
      }
      this.pipe.shift(); this.pipe.push(o);
      this.t++;
      return this.own;
    }
    settle(ticks) { this.wired = false; for (let k = 0; k < (ticks || 1500); k++) this.step(); this.wired = true; return this; }
  }

  function ringEdges(n, w, L) { return Array.from({ length: n }, (_, i) => [i, (i + 1) % n, w, L || 0]); }

  const api = { Net, ringEdges, qOf, OWN, WIRE, QMIN, QMAX, RELAY, CLOCK };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.GN27 = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
