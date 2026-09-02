import unittest
from financialjuice_bot.filters import actual_vs_forecast, impact_for


class FilterTests(unittest.TestCase):
    def test_extreme(self):
        self.assertEqual(impact_for("US CPI", 1), "EXTREME")

    def test_high_provider_importance(self):
        self.assertEqual(impact_for("Random Indicator", 3), "HIGH")

    def test_higher_is_better(self):
        result = actual_vs_forecast("Nonfarm Payrolls", "220K", "200K")
        self.assertIn("BETTER", result.label)

    def test_lower_is_better(self):
        result = actual_vs_forecast("CPI", "2.9%", "3.1%")
        self.assertIn("BETTER", result.label)

    def test_in_line(self):
        result = actual_vs_forecast("GDP", "2.00%", "2.01%")
        self.assertEqual(result.label, "IN LINE")


if __name__ == "__main__":
    unittest.main()
