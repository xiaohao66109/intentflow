import unittest
from maintenance import MaintenanceSystem

class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.s=MaintenanceSystem()
        self.t=self.s.act("resident-a","submit",title="厨房漏水",location="1 栋 201")["id"]
    def dispatch(self):
        self.s.act("dispatcher","accept",self.t)
        self.s.act("dispatcher","assign",self.t)
    def test_full_lifecycle(self):
        self.dispatch()
        self.s.act("worker-a","start",self.t)
        self.s.act("worker-a","complete",self.t,result="更换阀门，漏水停止")
        self.assertEqual(self.s.act("resident-a","close",self.t)["status"],"closed")
    def test_cancel_before_assignment(self):
        self.assertEqual(self.s.act("resident-a","cancel",self.t)["status"],"cancelled")
    def test_reopen_requires_reason(self):
        self.dispatch(); self.s.act("worker-a","start",self.t)
        self.s.act("worker-a","complete",self.t,result="检查完成")
        with self.assertRaises(ValueError): self.s.act("resident-a","reopen",self.t)
        self.assertEqual(self.s.act("resident-a","reopen",self.t,result="仍然漏水")["status"],"processing")
    def test_completion_requires_result(self):
        self.dispatch(); self.s.act("worker-a","start",self.t)
        with self.assertRaises(ValueError): self.s.act("worker-a","complete",self.t)
