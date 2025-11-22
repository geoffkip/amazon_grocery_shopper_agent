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

# --- STREAMLIT UI ---
PAGE_TITLE = "Amazon Fresh Fetch"
PAGE_ICON = "🥕"

STREAMLIT_STYLE = """
<style>
    .meal-card {
        background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px;
        padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 8px solid #ff4b4b; height: 100%;
    }
    .meal-header {
        font-size: 1.2rem; font-weight: 700; color: #1f1f1f; margin-bottom: 8px;
        display: flex; align-items: center;
    }
    .meal-body { font-size: 1rem; color: #4f4f4f; line-height: 1.5; }
    .icon { margin-right: 8px; }
</style>
"""

DEFAULT_PROMPT = (
    "You are a world-class nutritionist and meal planning expert. "
    "Create a tailored Monday-Friday meal plan (Breakfast, Lunch, Dinner) for 2 adults.\n\n"
    "**CORE CONSTRAINTS:**\n"
    "- **Dietary:** No Pork. Heart-healthy. Focus on whole grains and fresh produce.\n"
    "- **Nutrition:** Aim for ~30g protein per meal. Avoid sugar crashes (low glycemic index).\n"
    "- **Time:** Meals must be on the table in 30 mins or less (except 1 'long cook' meal allowed).\n"
    "- **Budget:** Mix premium cuts with budget-friendly staples.\n\n"
    "**MEAL CADENCE:**\n"
    "- **Dinner:** Cook fresh 3 nights a week.\n"
    "- **Lunch:** Use leftovers from dinner for most lunches. "
    "On non-leftover days, schedule quick sandwiches/wraps/salads.\n"
    "- **Breakfast:** Rotate between: Yogurt with whole grain toast, "
    "English muffins (PB/Jam/Avocado/Cheese), Eggs, or healthy Muffins.\n\n"
    "**PREFERENCES:**\n"
    "- **Cuisines:** Mexican, Mediterranean, Stir-fries.\n"
    "- **Cooking Style:** Sheet pan, One-pot, Grilling, Slow Cooker.\n"
    "- **Appliances Available:** Instant Pot, Rice Cooker.\n"
    "- **Protein Variety:** Chicken, Beef, Seafood (Tilapia, Salmon, Cod, Shrimp), Lamb.\n"
    "- **Vegetarian:** Include 1-2 vegetarian dinners per week.\n"
    "- **Red Meat Limit:** Maximum 1-2 times per week.\n\n"
    "**OUTPUT FORMAT:**\n"
    "Return a VALID JSON object with exactly one key: 'schedule'."
)
