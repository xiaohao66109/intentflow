"""Small independent campus project; public requirements, no IntentFlow imports."""
from threading import Lock


def ensure_authenticated(user):
    if not user:
        raise ValueError("请先登录")


class Activity:
    def __init__(self, capacity=2, approval=False):
        self.capacity, self.approval = capacity, approval
        self.members, self.pending = set(), set()
        self.lock = Lock()

    def enroll(self, user):
        ensure_authenticated(user)
        with self.lock:
            if user in self.members or len(self.members) >= self.capacity:
                return False
            self.members.add(user)
            return True

    def cancel(self, user):
        ensure_authenticated(user)
        with self.lock:
            if user not in self.members:
                return False
            if self.approval:
                self.pending.add(user)
            else:
                self.members.remove(user)
            return True

    def approve(self, user):
        ensure_authenticated(user)
        with self.lock:
            if user not in self.pending:
                return False
            self.pending.remove(user)
            self.members.remove(user)
            return True
