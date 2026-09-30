"""Half-open time intervals and atomic overlap checks."""
from threading import Lock


class Calendar:
    def __init__(self, capacity=1, window=(0, 1440)):
        self.capacity, self.window = capacity, window
        self.entries = {}
        self.lock = Lock()

    def reserve(self, user, start, end):
        if not user or not self.window[0] <= start < end <= self.window[1]:
            return False
        with self.lock:
            if user in self.entries:
                return False
            overlapping = [(s, e) for s, e in self.entries.values() if s < end and start < e]
            points = {start} | {s for s, _ in overlapping if start <= s < end}
            if any(sum(s <= p < e for s, e in overlapping) >= self.capacity for p in points):
                return False
            self.entries[user] = (start, end)
            return True

    def cancel(self, user):
        with self.lock:
            return self.entries.pop(user, None) is not None
