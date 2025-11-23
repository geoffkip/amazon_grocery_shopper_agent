"""
Main application entry point for Amazon Fresh Fetch Agent.

This Streamlit application orchestrates the interaction between the user, the AI agent,
and the browser automation tool. It handles the UI for meal planning, shopping list
review, and checkout handoff.
"""

import asyncio
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

# Load environment variables from .env file
load_dotenv()

# ==========================================
# 1. CREDENTIAL CHECK
# ==========================================
def get_api_key():
    """Get API key from Environment OR Sidebar"""
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        # If no .env file, show an input box in the sidebar
        with st.sidebar:
            st.divider()
            st.warning("🔑 API Key Required")
            api_key = st.text_input(
                "Enter Gemini API Key:", 
                type="password", 
                help="Get one at aistudio.google.com"
            )
            if api_key:
                os.environ["GOOGLE_API_KEY"] = api_key # Set for this session
                st.success("Key Accepted!")
                st.rerun() # Rerun to ensure key is picked up
            else:
                st.stop() # Stop execution until key is provided
    return api_key

# Call this early in your script
GOOGLE_API_KEY = get_api_key()

from config import (
    PAGE_ICON,
    PAGE_TITLE,
)
from database import db
from pdf_generator import generate_pdf
from prompts import DEFAULT_PROMPT
from ui import STREAMLIT_STYLE, render_plan_ui
from utils import get_api_key
from workflow import init_session_state

# ==========================================
# 1. CREDENTIAL CHECK
# ==========================================
# Call this early in your script
GOOGLE_API_KEY = get_api_key()

# ==========================================
# STREAMLIT UI SETUP
# ==========================================

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

st.markdown(
    STREAMLIT_STYLE,
    unsafe_allow_html=True,
)

# INIT GRAPH
init_session_state()

app = st.session_state.graph_app

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Settings")
    budget = st.number_input(
        "Weekly Budget ($)", value=float(db.get_setting("budget", "200.0")), step=10.0
    )
    pantry_val = db.get_setting("pantry", "")
    pantry = st.text_area("In Your Pantry", pantry_val)

    if st.button("Save Settings"):
        db.save_setting("budget", str(budget))
        db.save_setting("pantry", pantry)
        st.success("Saved!")

    st.divider()
    st.subheader("📜 History")

    if st.button("🗑️ Clear History"):
        db.delete_all_plans()
        st.session_state.pop("history_view", None)
        st.rerun()

    past_plans = db.get_recent_plans()
    for p in past_plans:
        if st.button(f"{p['date']} - {len(p['list'])} items", key=f"hist_{p['id']}"):
            st.session_state.history_view = p
            st.rerun()

st.title(f"{PAGE_ICON} {PAGE_TITLE} AI Agent")

# --- WEEKLY MEAL PLAN PROMPT ---

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit_run_final"

user_prompt = st.text_area("Meal Prompt", value=DEFAULT_PROMPT, height=200)

if st.button("📝 Generate Plan", type="primary"):
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "budget_limit": budget,
        "pantry_items": pantry,
        "total_cost": 0.0,
    }

    async def run_to_planning():
        """Run the agent workflow until the planning stage is complete."""
        async for _ in app.astream(initial_state, config):
            pass

    asyncio.run(run_to_planning())
    st.rerun()

# STATE HANDLING
config = {"configurable": {"thread_id": st.session_state.thread_id}}
try:
    snapshot = app.get_state(config)
    current_step = snapshot.next[0] if snapshot.next else None
except Exception:
    current_step = None


# --- CHECK VIEW MODE (HISTORY vs NEW) ---
if "history_view" in st.session_state:
    h_data = st.session_state.history_view
    st.info(f"📂 Viewing Past Plan from: **{h_data['date']}**")
    if st.button("⬅️ Back to New Plan"):
        del st.session_state.history_view
        st.rerun()
    render_plan_ui(h_data["json"])
    st.divider()
    st.subheader("🛒 Historic Shopping List")
    st.dataframe(h_data["list"])

# --- REVIEW PHASE (NEW PLAN) ---
elif current_step == "shopper":
    st.divider()
    data = snapshot.values
    render_plan_ui(data["meal_plan_json"])

    st.divider()
    c_head, c_pdf = st.columns([3, 1])
    with c_head:
        st.subheader("🛒 Confirm Ingredients")

    raw_list = data.get("shopping_list", [])
    df = pd.DataFrame({"Item": raw_list, "Buy": [True] * len(raw_list)})

    edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")
    final_list = edited_df[edited_df["Buy"] == True]["Item"].tolist()

    with c_pdf:
        try:
            pdf_bytes = generate_pdf(data["meal_plan_json"], final_list)
            st.download_button(
                label="📄 Download PDF Plan",
                data=pdf_bytes,
                file_name="plan.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            st.error("PDF Error")

    if st.button(f"✅ Shop for {len(final_list)} Items", type="primary"):
        db.save_plan(user_prompt, data["meal_plan_json"], final_list)
        app.update_state(config, {"shopping_list": final_list})

        async def resume():
            """Resume the agent workflow from the current state."""
            async for _ in app.astream(None, config):
                pass

        asyncio.run(resume())
        st.rerun()

# --- HANDOFF PHASE ===
elif current_step == "checkout":
    st.divider()
    st.subheader("🛑 Automation Complete")
    data = snapshot.values
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", f"${data['total_cost']:.2f}")
    c2.metric("Budget", f"${data['budget_limit']:.2f}")

    cart_c = len(data.get("cart_items", []))
    miss_c = len(data.get("missing_items", []))
    total = cart_c + miss_c
    rate = int((cart_c / total) * 100) if total > 0 else 0
    c3.metric("Success Rate", f"{rate}%")

    col_a, col_b = st.columns(2)
    with col_a:
        st.success(f"✅ **Added ({cart_c})**")
        if cart_c > 0:
            st.dataframe(
                pd.DataFrame(data.get("cart_items", []), columns=["Item"]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.write("None.")

    with col_b:
        st.error(f"❌ **Missed ({miss_c})**")
        if miss_c > 0:
            st.warning("⚠️ Check these manually.")
            st.dataframe(
                pd.DataFrame(data.get("missing_items", []), columns=["Item"]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.write("None.")

    st.divider()
    st.info(
        "👋 **Manual Handoff:** Please complete payment in the open browser window."
    )
    if st.button("Close"):
        asyncio.run(st.session_state.browser_tool.close())
