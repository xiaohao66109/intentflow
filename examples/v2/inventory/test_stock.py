import unittest
from concurrent.futures import ThreadPoolExecutor
from stock import Stock


class StockTests(unittest.TestCase):
    def test_quantity_and_duplicate_cancel(self):
        stock = Stock(3)
        self.assertTrue(stock.reserve("甲", 2))
        self.assertFalse(stock.reserve("乙", 2))
        self.assertTrue(stock.cancel("甲"))
        self.assertFalse(stock.cancel("甲"))
        self.assertEqual(stock.remaining, 3)

    def test_concurrent_deductions(self):
        stock = Stock(3)
        with ThreadPoolExecutor(10) as pool:
            results = list(pool.map(lambda i: stock.reserve(str(i), 1), range(10)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(stock.remaining, 0)

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            Stock().reserve("甲", -1)
