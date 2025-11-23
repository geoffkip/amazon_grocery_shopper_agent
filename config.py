"""
Configuration settings for the Amazon Fresh Fetch Agent.
"""

import os

# --- DATABASE ---
DB_NAME = "agent_data.db"

# --- BROWSER ---
SESSION_FILE = "amazon_session.json"
HEADLESS_MODE = False  # Set to True if you want headless in the future

# --- AI MODELS ---
PLANNER_MODEL = "gemini-2.5-pro"
SHOPPER_MODEL = "gemini-2.5-flash"
EXTRACTOR_MODEL = "gemini-2.5-pro"

# --- UI & PROMPTS MOVED TO ui.py AND prompts.py ---
PAGE_TITLE = "Amazon Fresh Fetch"
PAGE_ICON = "🥕"
