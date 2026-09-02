import unittest
from financialjuice_bot.instruments import infer_currency, markets_for_currency


class CalendarTests(unittest.TestCase):
    def test_usd_mapping(self):
        self.assertEqual(infer_currency("United States", "$"), "USD")
        self.assertIn("XAUUSD", markets_for_currency("USD", ("XAUUSD", "DXY", "EURUSD")))
        self.assertIn("EURUSD", markets_for_currency("EUR", ("XAUUSD", "EURUSD")))


if __name__ == "__main__":
    unittest.main()
