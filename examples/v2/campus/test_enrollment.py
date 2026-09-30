import unittest
from concurrent.futures import ThreadPoolExecutor
from enrollment import Activity


class EnrollmentTests(unittest.TestCase):
    def test_capacity_and_duplicates(self):
        activity = Activity(2)
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(activity.enroll, [str(i) for i in range(8)]))
        self.assertEqual(sum(results), 2)
        self.assertEqual(len(activity.members), 2)
        self.assertFalse(activity.enroll(next(iter(activity.members))))

    def test_authentication(self):
        with self.assertRaises(ValueError):
            Activity().enroll("")

    def test_cancel_requires_approval(self):
        activity = Activity(1, approval=True)
        activity.enroll("甲")
        activity.cancel("甲")
        self.assertFalse(activity.enroll("乙"))
        activity.approve("甲")
        self.assertTrue(activity.enroll("乙"))
