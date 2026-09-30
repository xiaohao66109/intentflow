"""Atomic quantity deductions for an independent small Python project."""
from threading import Lock


class Stock:
    def __init__(self, capacity=3):
        self.remaining = capacity
        self.orders = {}
        self.lock = Lock()

    def reserve(self, order, quantity):
        if not order or type(quantity) is not int or quantity <= 0:
            raise ValueError("订单和数量无效")
        with self.lock:
            if order in self.orders or quantity > self.remaining:
                return False
            self.orders[order] = quantity
            self.remaining -= quantity
            return True

    def cancel(self, order):
        with self.lock:
            quantity = self.orders.pop(order, 0)
            self.remaining += quantity
            return quantity > 0
