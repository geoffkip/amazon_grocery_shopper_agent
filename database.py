"""
Database management module for Amazon Fresh Agent.

This module handles all SQLite database interactions, including storing user settings
and saving/retrieving meal plans.
"""

import sqlite3
import json
from datetime import datetime


class DBManager:
    """
    Manages the SQLite database for the agent.

    Attributes:
        conn (sqlite3.Connection): The database connection object.
    """

    def __init__(self, db_name="agent_data.db"):
        """
        Initialize the DBManager.

        Args:
            db_name (str): The name of the database file. Defaults to "agent_data.db".
        """
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        """Create the necessary tables if they do not exist."""
        c = self.conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS settings 
                     (key TEXT PRIMARY KEY, value TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS meal_plans 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      date TEXT, 
                      prompt TEXT, 
                      plan_json TEXT, 
                      shopping_list TEXT)"""
        )
        self.conn.commit()

    def save_setting(self, key, value):
        """
        Save a user setting to the database.

        Args:
            key (str): The setting key.
            value (str): The setting value.
        """
        c = self.conn.cursor()
        c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get_setting(self, key, default=""):
        """
        Retrieve a user setting from the database.

        Args:
            key (str): The setting key.
            default (str): The default value if the key is not found.

        Returns:
            str: The setting value or the default.
        """
        c = self.conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = c.fetchone()
        return result[0] if result else default

    def save_plan(self, prompt, plan_json, shopping_list):
        """
        Save a generated meal plan to the database.

        Args:
            prompt (str): The user prompt used to generate the plan.
            plan_json (str): The JSON string of the meal plan.
            shopping_list (list): The list of shopping items.
        """
        c = self.conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        list_str = json.dumps(shopping_list)
        c.execute(
            "INSERT INTO meal_plans (date, prompt, plan_json, shopping_list) VALUES (?, ?, ?, ?)",
            (date_str, prompt, plan_json, list_str),
        )
        self.conn.commit()

    def get_recent_plans(self, limit=5):
        """
        Retrieve the most recent meal plans.

        Args:
            limit (int): The maximum number of plans to retrieve. Defaults to 5.

        Returns:
            list: A list of dictionaries containing plan details.
        """
        c = self.conn.cursor()
        c.execute(
            "SELECT id, date, prompt, plan_json, shopping_list FROM meal_plans ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "id": r[0],
                "date": r[1],
                "prompt": r[2],
                "json": r[3],
                "list": json.loads(r[4]),
            }
            for r in c.fetchall()
        ]

    def delete_all_plans(self):
        """Delete all saved meal plans from the database."""
        c = self.conn.cursor()
        c.execute("DELETE FROM meal_plans")
        self.conn.commit()

    # --- PREFERENCE LEARNING ---
    def get_all_past_items(self):
        """
        Retrieve all unique items from past shopping lists.

        Returns:
            str: A comma-separated string of all unique items.
        """
        c = self.conn.cursor()
        c.execute("SELECT shopping_list FROM meal_plans")
        rows = c.fetchall()
        all_items = set()
        for r in rows:
            try:
                items = json.loads(r[0])
                for i in items:
                    all_items.add(i.strip())
            except (json.JSONDecodeError, TypeError):
                pass
        return ", ".join(list(all_items))


db = DBManager()
