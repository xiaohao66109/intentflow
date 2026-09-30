import unittest
from maintenance import MaintenanceSystem
from readmodel import resident_detail

class PermissionTest(unittest.TestCase):
    def setUp(self):
        self.s=MaintenanceSystem(); self.t=self.s.act("resident-a","submit",title="灯故障",location="1 栋")["id"]
        self.s.act("dispatcher","accept",self.t); self.s.act("dispatcher","assign",self.t)
    def test_other_resident_cannot_read(self):
        with self.assertRaises(ValueError): resident_detail(self.s.state["tickets"][0],"resident-b")
    def test_wrong_worker_cannot_update(self):
        with self.assertRaises(ValueError): self.s.act("worker-b","set_contact",self.t,contact_at=630)
    def test_resident_cannot_assign(self):
        with self.assertRaises(ValueError): self.s.act("resident-a","assign",self.t)
    def test_assigned_ticket_cannot_cancel(self):
        with self.assertRaises(ValueError): self.s.act("resident-a","cancel",self.t)
    def test_time_bounds(self):
        with self.assertRaises(ValueError): self.s.act("worker-a","set_contact",self.t,at=600,contact_at=599)
        with self.assertRaises(ValueError): self.s.act("worker-a","set_contact",self.t,at=600,contact_at=2041)
        self.assertEqual(self.s.act("worker-a","set_contact",self.t,at=600,contact_at=2040)["expected_contact"],2040)
