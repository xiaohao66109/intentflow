import unittest
from booking import Calendar


class BookingTests(unittest.TestCase):
    def test_adjacent_and_overlapping(self):
        calendar = Calendar()
        self.assertTrue(calendar.reserve("甲", 0, 60))
        self.assertTrue(calendar.reserve("乙", 60, 120))
        self.assertFalse(calendar.reserve("丙", 59, 61))

    def test_window(self):
        self.assertFalse(Calendar().reserve("甲", -1, 60))
        self.assertFalse(Calendar().reserve("甲", 0, 1441))

    def test_parallel_disjoint_intervals(self):
        calendar = Calendar(capacity=2)
        calendar.reserve("甲", 0, 60)
        calendar.reserve("乙", 60, 120)
        self.assertTrue(calendar.reserve("丙", 0, 120))
