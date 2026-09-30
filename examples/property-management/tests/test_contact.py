import unittest
from copy import deepcopy
from readmodel import resident_detail

class ContactTest(unittest.TestCase):
    def ticket(self,status="assigned",time=630):
        return {"id":"BX-001","owner":"resident-a","title":"厨房漏水","status":status,"expected_contact":time,"result":""}
    def test_assigned_contact_visible(self):
        self.assertEqual(resident_detail(self.ticket(),"resident-a").get("contact_time"),630)
    def test_processing_uses_updated_time(self):
        self.assertEqual(resident_detail(self.ticket("processing",690),"resident-a").get("contact_time"),690)
    def test_empty_and_legacy(self):
        for t in [self.ticket(time=None), {k:v for k,v in self.ticket().items() if k!="expected_contact"}]:
            self.assertIsNone(resident_detail(t,"resident-a").get("contact_time"))
    def test_terminal_has_no_future_promise(self):
        for status in ["completed","closed","cancelled","submitted","accepted"]:
            self.assertIsNone(resident_detail(self.ticket(status),"resident-a").get("contact_time"))
    def test_query_does_not_mutate(self):
        t=self.ticket(); before=deepcopy(t);resident_detail(t,"resident-a");self.assertEqual(t,before)
