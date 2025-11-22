"""
Unit tests for database.py
"""

import json
import os
import tempfile
import unittest

from database import DBManager


class TestDBManager(unittest.TestCase):
    """Test cases for DBManager class."""

    def setUp(self):
        """Set up a temporary database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = DBManager(self.temp_db.name)

    def tearDown(self):
        """Clean up the temporary database."""
        self.db.conn.close()
        os.unlink(self.temp_db.name)

    def test_save_and_get_setting(self):
        """Test saving and retrieving settings."""
        self.db.save_setting("budget", "200.0")
        result = self.db.get_setting("budget")
        self.assertEqual(result, "200.0")

    def test_get_setting_default(self):
        """Test getting a non-existent setting returns default."""
        result = self.db.get_setting("nonexistent", "default_value")
        self.assertEqual(result, "default_value")

    def test_save_plan(self):
        """Test saving a meal plan."""
        test_plan = json.dumps({"schedule": [{"day": "Monday"}]})
        test_list = ["Eggs", "Bread"]
        self.db.save_plan("Test prompt", test_plan, test_list)

        plans = self.db.get_recent_plans(limit=1)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["prompt"], "Test prompt")
        self.assertEqual(plans[0]["json"], test_plan)
        self.assertEqual(plans[0]["list"], test_list)

    def test_get_recent_plans(self):
        """Test retrieving recent plans."""
        # Add multiple plans
        for i in range(3):
            self.db.save_plan(
                f"Prompt {i}",
                json.dumps({"schedule": []}),
                [f"Item {i}"]
            )

        plans = self.db.get_recent_plans(limit=2)
        self.assertEqual(len(plans), 2)
        # Most recent should be first
        self.assertEqual(plans[0]["prompt"], "Prompt 2")

    def test_delete_all_plans(self):
        """Test deleting all plans."""
        self.db.save_plan("Test", json.dumps({"schedule": []}), ["Item"])
        self.db.delete_all_plans()
        plans = self.db.get_recent_plans()
        self.assertEqual(len(plans), 0)

    def test_get_all_past_items(self):
        """Test retrieving all unique past items."""
        self.db.save_plan("Plan 1", json.dumps({"schedule": []}), ["Eggs", "Bread"])
        self.db.save_plan("Plan 2", json.dumps({"schedule": []}), ["Eggs", "Milk"])

        result = self.db.get_all_past_items()
        items = set(item.strip() for item in result.split(","))
        self.assertIn("Eggs", items)
        self.assertIn("Bread", items)
        self.assertIn("Milk", items)


if __name__ == "__main__":
    unittest.main()
