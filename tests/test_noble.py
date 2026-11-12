"""Fast checks of the Noble round (experiments/noble_n1_n2.py, experiments/noble_n3.py)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "experiments")]
import gn27 as g                      # noqa: E402
import noble_n1_n2 as n12             # noqa: E402
import noble_n3 as n3                 # noqa: E402


class Clamp(unittest.TestCase):
    def test_clampnet_unclamped_is_gn27(self):
        a = g.settle(g.Net([g.CLOCK, g.RELAY], [(0, 1, -6.0, 0)]), 300)
        b = g.settle(n12.ClampNet([g.CLOCK, g.RELAY], [(0, 1, -6.0, 0)]), 300)
        for _ in range(500):
            np.testing.assert_array_equal(a.step(), b.step())

    def test_clamping_the_slow_variable_stops_the_clock(self):
        free = n12.clock()[0]
        for v in (0.5, 0.0):
            beats = n12.clock(clamp=v)[0]
            self.assertTrue(all(e < 300 for e in beats), (v, beats))
        self.assertGreater(sum(e >= 300 for e in free), 8)

    def test_replayed_slow_trace_sets_the_beat_times_whatever_the_fast_state(self):
        free, tr = n12.clock()
        replay = lambda t: tr[(t - 601) % len(tr)]   # noqa: E731
        a = n12.clock(clamp=replay)[0]
        b = n12.clock(clamp=replay, scramble=3)[0]
        self.assertEqual(a, b)
        shifted = n12.clock(clamp=lambda t: tr[(t - 601 + 20) % len(tr)])[0]
        self.assertEqual([x for x in a if x > 330], [x + 20 for x in shifted if x > 310])


class DualRole(unittest.TestCase):
    def test_constant_1_1_relays_and_escapes(self):
        r = n12.drive(lambda: g.settle(g.Net([1.1]), 1500), 32)
        self.assertEqual(r["answered"], 1.0)
        self.assertEqual(r["extra_beats_while_driven"], 0)
        self.assertEqual(r["first_beat_after_input_stops"], 64)

    def test_relay_1_6_and_window_never_escape(self):
        self.assertIsNone(n12.drive(lambda: g.settle(g.Net([1.6]), 1500), 32)["first_beat_after_input_stops"])
        self.assertIsNone(n12.drive(lambda: n12.WindowNet([1.6]), 32)["first_beat_after_input_stops"])


class FourSituations(unittest.TestCase):
    def test_hold_world_gone_ring_talking(self):
        r = n3.report("hold", n3.run("hold"))
        P2 = 1
        self.assertGreaterEqual(r["beats_per_phase"]["comparator"][P2], 55)          # sees the missing world
        self.assertEqual(r["escape_beats_per_phase"]["ring_watchdog"][P2], 0)       # fooled by the ring
        self.assertEqual(r["escape_beats_per_phase"]["world_watchdog"][P2], 10)     # world is silent
        self.assertGreater(r["escape_beats_per_phase"]["ring_watchdog"][2], 5)      # everything silent
        self.assertTrue(r["P4_ring_matches_world_last_lap"])


if __name__ == "__main__":
    unittest.main()
