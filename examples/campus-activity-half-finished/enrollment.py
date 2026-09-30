"""In-memory activity registration."""
import time

class Activity:
    def __init__(self, capacity=30):
        self.capacity = capacity
        self.members = set()

    def enroll(self, user):
        if user in self.members or len(self.members) >= self.capacity:
            return False
        time.sleep(0.005)
        self.members.add(user)
        return True

    def cancel(self, user):
        self.members.discard(user)
