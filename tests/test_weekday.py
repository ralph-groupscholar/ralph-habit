import unittest
from datetime import date

import habit


class WeekdaySummaryTests(unittest.TestCase):
    def test_weekday_summary_with_schedule(self):
        end_date = date(2026, 2, 7)
        window = habit._window_dates(end_date, 7)
        checkins = {"2026-02-01", "2026-02-03"}
        target_days = ["mon", "wed", "fri"]

        actual, expected, total_actual, total_expected = habit._weekday_summary(
            window, checkins, target_days
        )

        self.assertEqual(total_actual, 2)
        self.assertEqual(total_expected, 3)
        self.assertEqual(actual["sun"], 1)
        self.assertEqual(actual["tue"], 1)
        self.assertEqual(expected["mon"], 1)
        self.assertEqual(expected["wed"], 1)
        self.assertEqual(expected["fri"], 1)
        self.assertEqual(expected["sun"], 0)

    def test_weekday_summary_without_schedule(self):
        end_date = date(2026, 2, 7)
        window = habit._window_dates(end_date, 7)
        checkins = {"2026-02-02", "2026-02-04", "2026-02-06"}

        actual, expected, total_actual, total_expected = habit._weekday_summary(
            window, checkins, []
        )

        self.assertEqual(total_actual, 3)
        self.assertEqual(total_expected, 7)
        self.assertEqual(actual["mon"], 1)
        self.assertEqual(actual["wed"], 1)
        self.assertEqual(actual["fri"], 1)
        self.assertEqual(expected["mon"], 1)
        self.assertEqual(expected["sun"], 1)


if __name__ == "__main__":
    unittest.main()
