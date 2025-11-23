"""
UI components and styles for the Amazon Fresh Fetch Agent.
"""

import json
import pandas as pd
import streamlit as st

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
