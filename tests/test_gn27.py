"""Fast checks of the v27 claims (about 30 seconds). The full numbers are experiments/v27.py."""
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from gn27 import RELAY, Beats, Net, pulse, read, rings, settle, write  # noqa: E402


class SameMachine(unittest.TestCase):
    def test_matches_round_ten_simulator(self):
        """With no cable length gn27.Net is native.py of GeometricNeuronSurfaceListener, tick for tick."""
        fx = json.loads((ROOT / "tests" / "native_fixture.json").read_text())
        for name, c in fx.items():
            edges = []
            for i in range(3):
                edges.append((i, i + 1, c["w"], 0))
                if c["two_way"]:
                    edges.append((i + 1, i, c["w"], 0))
            net = Net([1.0, RELAY, RELAY, RELAY], edges, seed=c["seed"])
            det, tot = Beats(4), np.zeros(4)
            for k in range(3000):
                own = net.step()
                tot += own
                det.see(own, k)
            self.assertEqual(det.ev, c["beats"], name)
            np.testing.assert_allclose(tot, c["sum_of_own"], rtol=0, atol=1e-9, err_msg=name)

    def test_page_fixture_is_current(self):
        import make_fixture
        fx = json.loads((ROOT / "tests" / "fixture.json").read_text())
        for name, case in make_fixture.CASES.items():
            self.assertEqual(make_fixture.play(case), fx["cases"][name]["beats"], name)


class RingMemory(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(7)

    def test_ring_keeps_random_patterns(self):
        net, off = rings([(8, -6.0, 0)] * 6)
        bits = (self.rng.random((6, 32)) < 0.4).astype(int)
        write(net, off, bits)
        first = read(net, off, 32)
        for _ in range(200):
            last = read(net, off, 32)
        np.testing.assert_array_equal(first, np.roll(bits, 4, axis=1))
        np.testing.assert_array_equal(first, last)

    def test_one_unit_one_cable(self):
        net, off = rings([(1, -6.0, 55)] * 4)
        bits = (self.rng.random((4, 59)) < 0.3).astype(int)
        write(net, off, bits)
        first = read(net, off, 59)
        for _ in range(100):
            last = read(net, off, 59)
        np.testing.assert_array_equal(first, np.roll(bits, 4, axis=1))
        np.testing.assert_array_equal(first, last)

    def test_hole_at_minus_5_5(self):
        net, off = rings([(8, -5.5, 0)])
        write(net, off, np.array([[1, 1] + [0] * 30]))
        for _ in range(20):
            last = read(net, off, 32)
        self.assertEqual(int(last.sum()), 0)

    def test_signal_in_rhythm_does_not_erase_but_setpoint_does(self):
        net, off = rings([(8, -6.0, 0)] * 2)
        bits = (self.rng.random((2, 32)) < 0.4).astype(int)
        write(net, off, bits)
        a = read(net, off, 32)
        for _ in range(10):
            read(net, off, 32, ext=lambda k: np.full(net.n, 0.2 * (1 if net.t % 8 < 4 else -1)))
        np.testing.assert_array_equal(a, read(net, off, 32))

        def raise_first(k):
            v = np.zeros(net.n)
            v[off] = 12.0
            return v
        read(net, off, 32, sp=raise_first)
        self.assertEqual(int(read(net, off, 32).sum()), 0)

    def test_one_tick_erases_one_bit(self):
        net, off = rings([(8, -6.0, 0)])
        bits = (self.rng.random((1, 32)) < 0.4).astype(int)
        write(net, off, bits)
        a = read(net, off, 32)
        t = int(np.flatnonzero(a[0])[0])

        def one(k):
            v = np.zeros(net.n)
            if k == (t - 4) % 32:
                v[0] = 12.0
            return v
        read(net, off, 32, sp=one)
        want = a.copy()
        want[0, t] = 0
        np.testing.assert_array_equal(read(net, off, 32), want)


class Cable(unittest.TestCase):
    def test_distance_selects_the_listener(self):
        Ls = list(range(41))
        n = 1 + len(Ls)
        net = settle(Net(np.full(n, RELAY), [(0, 1 + k, -24.0, L) for k, L in enumerate(Ls)], lam=10.0))
        det = Beats(n)
        for k in range(120):
            det.see(net.step(sp_ext=pulse(n, 0, k, 5)), k)
        self.assertEqual([L for k, L in enumerate(Ls) if det.ev[1 + k]], [8, 13, 14, 15, 16, 17])


if __name__ == "__main__":
    unittest.main()
