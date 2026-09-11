import unittest
from datetime import date

import water_monitoring as wm


class USPLimitTests(unittest.TestCase):
    def test_exact_table_points(self):
        self.assertAlmostEqual(wm.usp_conductivity_limit(25), 1.3)
        self.assertAlmostEqual(wm.usp_conductivity_limit(20), 1.1)
        self.assertAlmostEqual(wm.usp_conductivity_limit(0), 0.6)

    def test_interpolation(self):
        # halfway between 20 (1.1) and 25 (1.3) -> 1.2
        self.assertAlmostEqual(wm.usp_conductivity_limit(22.5), 1.2)

    def test_clamping(self):
        self.assertEqual(wm.usp_conductivity_limit(-10), 0.6)
        self.assertEqual(wm.usp_conductivity_limit(120), 4.1)

    def test_passes_usp(self):
        self.assertTrue(wm.passes_usp(25.0, 1.29))
        self.assertFalse(wm.passes_usp(25.0, 1.31))
        # warmer water allows more conductivity under stage 1
        self.assertTrue(wm.passes_usp(80.0, 3.0))

    def test_passes_usp_guards(self):
        with self.assertRaises(ValueError):
            wm.passes_usp(50, -1)


class RejectionTests(unittest.TestCase):
    def test_rejection(self):
        # feed 400, product 8 -> 98% rejection
        self.assertAlmostEqual(wm.rejection_pct(400, 8), 98.0)

    def test_salt_passage(self):
        self.assertAlmostEqual(wm.salt_passage_pct(400, 8), 2.0)

    def test_rejection_guards(self):
        with self.assertRaises(ValueError):
            wm.rejection_pct(0, 5)
        with self.assertRaises(ValueError):
            wm.rejection_pct(5, 6)


class SanitizationTests(unittest.TestCase):
    def test_in_spec(self):
        s = wm.sanitization_status(date(2026, 8, 15), 30, date(2026, 9, 1))
        self.assertEqual(s["status"], "in spec")
        self.assertEqual(s["days_left"], 13)
        self.assertEqual(s["next_due"], "2026-09-14")

    def test_due_soon(self):
        s = wm.sanitization_status(date(2026, 8, 15), 30, date(2026, 9, 9))
        self.assertEqual(s["status"], "due soon")
        self.assertEqual(s["days_left"], 5)

    def test_overdue(self):
        s = wm.sanitization_status(date(2026, 8, 1), 20, date(2026, 9, 1))
        self.assertEqual(s["status"], "overdue")
        self.assertLess(s["days_left"], 0)

    def test_done_today(self):
        s = wm.sanitization_status(date(2026, 9, 9), 30, date(2026, 9, 9))
        self.assertEqual(s["status"], "done today")
        self.assertEqual(s["days_since"], 0)

    def test_iso_input(self):
        s = wm.sanitization_status("2026-08-15", 30, "2026-09-09")
        self.assertEqual(s["status"], "due soon")

    def test_guards(self):
        with self.assertRaises(ValueError):
            wm.sanitization_status(date(2026, 9, 9), 30, date(2026, 9, 1))


class SeriesTests(unittest.TestCase):
    def test_stats_and_exceedances(self):
        records = [
            (date(2026, 9, 1), 25.0, 0.9),
            (date(2026, 9, 2), 25.0, 1.1),
            (date(2026, 9, 3), 25.0, 1.4),   # exceeds 1.3 limit at 25C
        ]
        s = wm.series_stats(records)
        self.assertEqual(s["count"], 3)
        self.assertAlmostEqual(s["conductivity"]["mean"], 1.133333, places=5)
        self.assertEqual(len(s["usp_exceedances"]), 1)
        self.assertEqual(s["usp_exceedances"][0][2], 1.4)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            wm.series_stats([])


class DemoDataTests(unittest.TestCase):
    def test_demo_readings_well_behaved(self):
        stats = wm.series_stats(wm.DEMO_READINGS)
        self.assertEqual(stats["count"], 30)
        for r in wm.DEMO_READINGS:
            self.assertTrue(0.5 <= r[2] <= 1.5)
        # the demo deliberately ends with rising conductivity: exceedances
        # must all land on the final two days (the signal to sanitise)
        self.assertTrue(stats["usp_exceedances"])
        bad_days = sorted({r[0] for r in stats["usp_exceedances"]})
        self.assertEqual(bad_days, [date(2026, 9, 7), date(2026, 9, 8)])


if __name__ == "__main__":
    unittest.main()