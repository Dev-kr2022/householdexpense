import unittest
from datetime import date

import pandas as pd

import app


class ReportFeatureTests(unittest.TestCase):
    def test_monthly_category_report_groups_values_by_month_and_category(self):
        expenses = pd.DataFrame(
            [
                {"Date": "2024-01-05", "Category": "Food", "Amount": 80.0},
                {"Date": "2024-01-10", "Category": "Food", "Amount": 40.0},
                {"Date": "2024-02-03", "Category": "House Help", "Amount": 50.0},
            ]
        )

        report = app.build_monthly_category_report(expenses)

        self.assertEqual(report.columns.tolist(), ["Month", "Category", "Amount"])
        self.assertEqual(report.loc[(report["Month"] == "2024-01") & (report["Category"] == "Food"), "Amount"].iloc[0], 120.0)

    def test_monthly_average_summary_includes_average_expense(self):
        expenses = pd.DataFrame(
            [
                {"Date": "2024-01-05", "Category": "Food", "Amount": 80.0},
                {"Date": "2024-01-10", "Category": "Food", "Amount": 40.0},
                {"Date": "2024-02-03", "Category": "House Help", "Amount": 50.0},
            ]
        )

        summary = app.build_monthly_average_summary(expenses)

        self.assertIn("Average Expense", summary.columns)
        self.assertAlmostEqual(summary.loc[summary["Month"] == "2024-01", "Average Expense"].iloc[0], 60.0)

    def test_monthly_category_range_is_limited_to_twelve_calendar_months(self):
        self.assertEqual(app.monthly_category_range_months(date(2025, 9, 1), date(2026, 8, 31)), 12)
        self.assertEqual(app.monthly_category_range_months(date(2025, 8, 1), date(2026, 8, 31)), 13)

    def test_database_context_includes_all_transactions(self):
        expenses = pd.DataFrame(
            [
                {"Date": "2024-01-05", "Category": "Food", "User": "RN", "Amount": 80.0, "Note": "breakfast"},
                {"Date": "2024-02-03", "Category": "Petrol", "User": "DK", "Amount": 50.0, "Note": "fuel"},
            ]
        )

        context = app.database_context(expenses)

        self.assertIn("breakfast", context)
        self.assertIn("fuel", context)


if __name__ == "__main__":
    unittest.main()
