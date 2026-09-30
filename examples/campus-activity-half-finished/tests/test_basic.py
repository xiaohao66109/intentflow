import unittest
from auth import login
from enrollment import Activity

class BasicTests(unittest.TestCase):
    def test_login(self):
        self.assertTrue(login("student", "campus-demo"))
        self.assertFalse(login("student", "wrong"))

    def test_enrollment_and_cancel(self):
        a = Activity(2)
        self.assertTrue(a.enroll("u1"))
        self.assertFalse(a.enroll("u1"))
        a.cancel("u1")
        self.assertEqual(len(a.members), 0)
