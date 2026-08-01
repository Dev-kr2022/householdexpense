import os
import unittest
from unittest.mock import patch

import app


class DatabaseConfigTests(unittest.TestCase):
    def test_detects_postgres_database_url(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@db.supabase.co:5432/postgres"}, clear=True):
            self.assertEqual(app.get_database_kind(), "postgres")

    def test_defaults_to_sqlite_when_no_database_url_is_set(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app.get_database_kind(), "sqlite")

    def test_postgres_schema_uses_safe_column_name(self):
        self.assertIn("expense_user", app.POSTGRES_TABLE_SQL)
        self.assertNotIn(" user TEXT", app.POSTGRES_TABLE_SQL)

    def test_postgres_query_uses_placeholder_syntax(self):
        categories = ["Grocery", "Electricity"]
        users = ["RN", "DK"]
        query, params = app.build_expense_query(categories, users, is_postgres=True)
        self.assertIn("%s", query)
        self.assertEqual(len(params), 4)


if __name__ == "__main__":
    unittest.main()
