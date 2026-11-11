"""Write tests/fixture.json: beat ticks from gn27.py that v27.js must reproduce exactly."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gn27 import CLOCK, RELAY, Beats, Net, ring_edges, settle  # noqa: E402

CASES = {
    "ring of 8, weight -6": dict(const=[RELAY] * 8, edges=ring_edges(8, -6.0), lam=None),
    "ring of 4, weight -5": dict(const=[RELAY] * 4, edges=ring_edges(4, -5.0), lam=None),
    "one unit, cable 55, clock gate": dict(const=[RELAY, CLOCK], edges=ring_edges(1, -6.0, 55) + [(1, 0, 6.0, 0)], lam=None),
    "one unit, cable 56, clock gate": dict(const=[RELAY, CLOCK], edges=ring_edges(1, -6.0, 56) + [(1, 0, 6.0, 0)], lam=None),
    "attenuated ring": dict(const=[RELAY] * 4, edges=ring_edges(4, -6.5, 3), lam=20.0),
    "clock into two-way chain with self-cables": dict(
        const=[CLOCK] + [RELAY] * 4,
        edges=[e for i in range(4) for e in ((i, i + 1, -6.0, 0), (i + 1, i, -6.0, 0))] + [(i, i, 12.0, 4) for i in range(5)], lam=None),
}
BITS = [1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0, 0]


def play(case, ticks=4000):
    net = settle(Net(case["const"], case["edges"], lam=case["lam"]))
    det = Beats(net.n)
    for k in range(ticks):
        sp = np.zeros(net.n)
        if k < len(BITS):
            sp[0] = -10.0 * BITS[k]
        det.see(net.step(sp_ext=sp), k)
    return [[int(t) for t in e] for e in det.ev]


if __name__ == "__main__":
    out = {"bits": BITS, "cases": {k: {**v, "beats": play(v)} for k, v in CASES.items()}}
    (ROOT / "tests" / "fixture.json").write_text(json.dumps(out))
    print({k: [len(e) for e in v["beats"]] for k, v in out["cases"].items()})
