"""
Main application entry point for Amazon Fresh Fetch Agent.

This Streamlit application orchestrates the interaction between the user, the AI agent,
and the browser automation tool. It handles the UI for meal planning, shopping list
review, and checkout handoff.
"""

import asyncio
import json

import pandas as pd
import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent import (
    AgentState,
    checkout_node,
    extractor_node,
    human_review_node,
    planner_node,
    shopper_node,
)
from browser import AmazonFreshBrowser
from database import db
from pdf_generator import generate_pdf

# ==========================================
# STREAMLIT UI SETUP
# ==========================================

st.set_page_config(page_title="Amazon Fresh Fetch", page_icon="🥕", layout="wide")

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# INIT GRAPH
if "graph_app" not in st.session_state:
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("shopper", shopper_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("checkout", checkout_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "extractor")
    workflow.add_edge("extractor", "shopper")
    workflow.add_edge("shopper", "human_review")
    workflow.add_edge("human_review", "checkout")
    workflow.add_edge("checkout", END)
    st.session_state.graph_app = workflow.compile(
        checkpointer=MemorySaver(), interrupt_before=["shopper", "checkout"]
    )
    st.session_state.browser_tool = AmazonFreshBrowser()

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

st.title("🥕 Amazon Fresh Fetch AI Agent")

# --- WEEKLY MEAL PLAN PROMPT ---
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


# --- HELPER TO RENDER PLAN ---
def render_plan_ui(plan_json):
    """
    Render the meal plan in the Streamlit UI.

    Args:
        plan_json (str): The JSON string of the meal plan.
    """
    try:
        plan_data = json.loads(plan_json)
        schedule = plan_data.get("schedule", [])
        if schedule:
            nutri_data = []
            for day in schedule:
                n = day.get("nutrition", {})
                nutri_data.append(
                    {
                        "Day": day["day"],
                        "Calories": n.get("calories", 0),
                        "Protein": n.get("protein_g", 0),
                        "Carbs": n.get("carbs_g", 0),
                        "Fat": n.get("fat_g", 0),
                    }
                )
            if nutri_data:
                df_nutri = pd.DataFrame(nutri_data)
                st.subheader("📊 Nutritional Analysis")
                c1, c2 = st.columns(2)
                with c1:
                    st.bar_chart(df_nutri.set_index("Day")["Calories"], color="#ff4b4b")
                with c2:
                    st.bar_chart(df_nutri.set_index("Day")[["Protein", "Carbs", "Fat"]])

            st.subheader("📅 Weekly Plan")
            tabs = st.tabs([day["day"] for day in schedule])
            for tab, day_info in zip(tabs, schedule):
                with tab:
                    col1, col2, col3 = st.columns(3)

                    def get_title(m):
                        return m.get("title", str(m)) if isinstance(m, dict) else str(m)

                    with col1:
                        st.markdown(
                            f"""<div class="meal-card"><div class="meal-header"><span class="icon">🥞</span> Breakfast</div><div class="meal-body">{get_title(day_info.get('breakfast'))}</div></div>""",
                            unsafe_allow_html=True,
                        )
                    with col2:
                        st.markdown(
                            f"""<div class="meal-card"><div class="meal-header"><span class="icon">🥗</span> Lunch</div><div class="meal-body">{get_title(day_info.get('lunch'))}</div></div>""",
                            unsafe_allow_html=True,
                        )
                    with col3:
                        st.markdown(
                            f"""<div class="meal-card"><div class="meal-header"><span class="icon">🍳</span> Dinner</div><div class="meal-body">{get_title(day_info.get('dinner'))}</div></div>""",
                            unsafe_allow_html=True,
                        )

                    with st.expander("👨‍🍳 View Cooking Instructions"):
                        st.json(day_info)
    except Exception as e:
        st.error(f"Error rendering plan: {e}")


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
    final_list = edited_df[edited_df["Buy"] is True]["Item"].tolist()

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
                width=None,
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
                width=None,
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
