import unittest
from datetime import date

import habit


class StreakHelpersTests(unittest.TestCase):
    def test_streak_row_basic(self):
        item = {
            "id": 3,
            "title": "Hydrate",
            "checkins": ["2026-02-01", "2026-02-05", "2026-02-06", "2026-02-07"],
        }
        target_date = date(2026, 2, 7)
        row = habit._streak_row(item, target_date)

        self.assertEqual(row["id"], 3)
        self.assertEqual(row["title"], "Hydrate")
        self.assertEqual(row["current"], 3)
        self.assertEqual(row["longest"], 3)
        self.assertEqual(row["total"], 4)
        self.assertEqual(row["last_date"], date(2026, 2, 7))
        self.assertEqual(row["days_since"], 0)

    def test_streak_sort_key_modes(self):
        rows = [
            {"id": 2, "title": "Beta", "current": 1, "longest": 4},
            {"id": 1, "title": "Alpha", "current": 3, "longest": 3},
            {"id": 3, "title": "Gamma", "current": 2, "longest": 5},
        ]

        current_sorted = sorted(rows, key=lambda row: habit._streak_sort_key(row, "current"))
        self.assertEqual([row["id"] for row in current_sorted], [1, 3, 2])

        longest_sorted = sorted(rows, key=lambda row: habit._streak_sort_key(row, "longest"))
        self.assertEqual([row["id"] for row in longest_sorted], [3, 2, 1])

        title_sorted = sorted(rows, key=lambda row: habit._streak_sort_key(row, "title"))
        self.assertEqual([row["id"] for row in title_sorted], [1, 2, 3])

        id_sorted = sorted(rows, key=lambda row: habit._streak_sort_key(row, "id"))
        self.assertEqual([row["id"] for row in id_sorted], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
