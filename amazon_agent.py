import streamlit as st
import os
import asyncio
import json
import re
import sqlite3
import pandas as pd
import altair as alt
from datetime import datetime
from dotenv import load_dotenv
from typing import List, TypedDict, Annotated, Dict
from operator import add
from fpdf import FPDF

# LangChain / LangGraph imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from playwright.async_api import async_playwright

# Load Env
load_dotenv()

# ==========================================
# 1. DATABASE MANAGER (SQLite)
# ==========================================
class DBManager:
    def __init__(self, db_name="agent_data.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS settings 
                     (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS meal_plans 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      date TEXT, 
                      prompt TEXT, 
                      plan_json TEXT, 
                      shopping_list TEXT)''')
        self.conn.commit()

    def save_setting(self, key, value):
        c = self.conn.cursor()
        c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get_setting(self, key, default=""):
        c = self.conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = c.fetchone()
        return result[0] if result else default

    def save_plan(self, prompt, plan_json, shopping_list):
        c = self.conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        list_str = json.dumps(shopping_list)
        c.execute("INSERT INTO meal_plans (date, prompt, plan_json, shopping_list) VALUES (?, ?, ?, ?)",
                  (date_str, prompt, plan_json, list_str))
        self.conn.commit()

    def get_recent_plans(self, limit=5):
        c = self.conn.cursor()
        c.execute("SELECT id, date, prompt, plan_json, shopping_list FROM meal_plans ORDER BY id DESC LIMIT ?", (limit,))
        return [{"id": r[0], "date": r[1], "prompt": r[2], "json": r[3], "list": json.loads(r[4])} for r in c.fetchall()]

    def delete_all_plans(self):
        c = self.conn.cursor()
        c.execute("DELETE FROM meal_plans")
        self.conn.commit()

    # --- PREFERENCE LEARNING ---
    def get_all_past_items(self):
        c = self.conn.cursor()
        c.execute("SELECT shopping_list FROM meal_plans")
        rows = c.fetchall()
        all_items = set()
        for r in rows:
            try:
                items = json.loads(r[0])
                for i in items: all_items.add(i.strip())
            except: pass
        return ", ".join(list(all_items))

db = DBManager()

# ==========================================
# 2. STATE & BROWSER
# ==========================================

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add]
    meal_plan_json: str     
    shopping_list: List[str]
    cart_items: List[str]
    missing_items: List[str]
    user_approved: bool
    total_cost: float
    budget_limit: float
    pantry_items: str

class AmazonFreshBrowser:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.session_file = "amazon_session.json"

    async def start(self):
        if self.page: return 
        st.toast("🚀 Launching Browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False, slow_mo=1000)
        
        if os.path.exists(self.session_file):
            self.context = await self.browser.new_context(storage_state=self.session_file, viewport={"width": 1280, "height": 720})
            st.toast("🍪 Session loaded")
        else:
            self.context = await self.browser.new_context(viewport={"width": 1280, "height": 720})

        self.page = await self.context.new_page()
        await self.page.goto("https://www.amazon.com/alm/storefront?almBrandId=QW1hem9uIEZyZXNo")
        
        try:
            if await self.page.locator("#nav-link-accountList-nav-line-1").filter(has_text="Sign in").count() > 0:
                st.warning("⚠️ Please Log In manually in the browser window!")
                await asyncio.sleep(60)
                await self.context.storage_state(path=self.session_file)
        except: pass
        st.success("✅ Browser Ready")

    # --- BRUTE FORCE ADD ---
    async def search_and_add(self, item_name: str) -> dict:
        try:
            search_box = self.page.locator('input[id="twotabsearchtextbox"]')
            await search_box.clear()
            await search_box.fill(item_name)
            await search_box.press('Enter')
            try: await self.page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=3000)
            except: pass

            results = await self.page.locator('div[data-component-type="s-search-result"]').all()
            if not results: return {"status": "NOT_FOUND", "price": 0.0}
            target_card = results[0]

            price = 0.0
            try:
                price_el = target_card.locator(".a-price .a-offscreen").first
                if await price_el.count() > 0:
                    txt = await price_el.text_content()
                    price = float(txt.replace("$", "").replace(",", "").strip())
            except: pass

            btn = target_card.get_by_role("button", name="Add to cart")
            if await btn.count() == 0: btn = target_card.locator("button[name='submit.addToCart']")
            if await btn.count() == 0: btn = target_card.locator("input[name='submit.addToCart']")

            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                await asyncio.sleep(2)
                return {"status": "ADDED", "price": price}
            
            return {"status": "NOT_FOUND", "price": 0.0}
        except Exception as e:
            return {"status": f"ERROR", "price": 0.0}

    # --- SMART SHOPPER LOGIC ---
    async def search_and_get_options(self, item_name: str) -> List[Dict]:
        try:
            search_box = self.page.locator('input[id="twotabsearchtextbox"]')
            await search_box.clear()
            await search_box.fill(item_name)
            await search_box.press('Enter')
            try: await self.page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=3000)
            except: pass

            results = await self.page.locator('div[data-component-type="s-search-result"]').all()
            options = []
            for i, res in enumerate(results[:3]): 
                try:
                    title = await res.locator("h2").first.text_content()
                    price_text = "0.00"
                    if await res.locator(".a-price .a-offscreen").count() > 0:
                        price_text = await res.locator(".a-price .a-offscreen").first.text_content()
                    options.append({
                        "index": i,
                        "title": title.strip(),
                        "price_str": price_text.strip(),
                        "price": float(price_text.replace("$", "").replace(",", "").strip()) if "$" in price_text else 0.0
                    })
                except: continue
            return options
        except: return []

    async def add_specific_item(self, index: int) -> bool:
        try:
            results = await self.page.locator('div[data-component-type="s-search-result"]').all()
            if index >= len(results): return False
            target = results[index]
            
            btn = target.get_by_role("button", name="Add to cart")
            if await btn.count() == 0: btn = target.locator("button[name='submit.addToCart']")
            if await btn.count() == 0: btn = target.locator("input[name='submit.addToCart']")
            
            if await btn.count() > 0:
                await btn.first.scroll_into_view_if_needed()
                if await btn.first.is_visible():
                    await btn.first.click()
                    await asyncio.sleep(1)
                    return True
            return False
        except: return False

    async def trigger_checkout(self):
        st.toast("🛒 Going to Cart...")
        await self.page.goto("https://www.amazon.com/gp/cart/view.html")
        await asyncio.sleep(3)
        st.toast("➡️ Clicking 'Check out Fresh Cart'...")
        try:
            fresh_btn = self.page.get_by_role("button", name="Check out Fresh Cart")
            if await fresh_btn.count() > 0:
                await fresh_btn.click()
                return True
            proceed_btn = self.page.locator("input[name='proceedToALMCheckout-QW1hem9uIEZyZXNo']")
            if await proceed_btn.count() > 0:
                await proceed_btn.click()
                return True
            fallback = self.page.get_by_role("button", name="Proceed to checkout")
            if await fallback.count() > 0:
                await fallback.click()
                return True
        except: return False
        return False

    async def close(self):
        if self.context: await self.context.storage_state(path=self.session_file)
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

# ==========================================
# 3. PDF GENERATOR
# ==========================================
class MealPlanPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Amazon Fresh Fetch - Weekly Plan', 0, 1, 'C')
        self.ln(5)
    def clean_text(self, text):
        if not text: return ""
        return text.encode('latin-1', 'replace').decode('latin-1')

def generate_pdf(meal_json_str: str, shopping_list: List[str]) -> bytes:
    pdf = MealPlanPDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Master Shopping List', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    col_width = 90
    for i in range(0, len(shopping_list), 2):
        item1 = shopping_list[i]
        item2 = shopping_list[i+1] if i+1 < len(shopping_list) else ""
        pdf.cell(col_width, 7, f"[ ] {pdf.clean_text(item1)}", 0, 0)
        if item2: pdf.cell(col_width, 7, f"[ ] {pdf.clean_text(item2)}", 0, 1)
        else: pdf.ln(7)
    pdf.ln(10)

    try:
        data = json.loads(meal_json_str)
        schedule = data.get("schedule", [])
        for day in schedule:
            pdf.add_page()
            pdf.set_font('Arial', 'B', 16)
            pdf.set_text_color(255, 75, 75)
            pdf.cell(0, 10, pdf.clean_text(day['day']), 0, 1, 'L')
            pdf.set_text_color(0, 0, 0)
            for meal_type in ['breakfast', 'lunch', 'dinner']:
                meal_data = day.get(meal_type)
                if isinstance(meal_data, dict):
                    pdf.set_font('Arial', 'B', 12)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(0, 8, f"{meal_type.title()}: {pdf.clean_text(meal_data.get('title', ''))}", 0, 1, 'L', fill=True)
                    pdf.set_font('Arial', '', 10)
                    pdf.multi_cell(0, 5, f"Ing: {pdf.clean_text(meal_data.get('ingredients', ''))}")
                    pdf.multi_cell(0, 5, f"Steps: {pdf.clean_text(meal_data.get('instructions', ''))}")
                    pdf.ln(5)
    except: pass
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. NODES
# ==========================================

async def planner_node(state: AgentState):
    with st.status("🧠 Planner: Designing Schedule & Analyzing Nutrition...", expanded=True) as status:
        # Gemini 2.5 Pro with higher temperature for a bit of creativity
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.7, google_api_key=os.getenv("GOOGLE_API_KEY"))
        # Meal Planner Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional chef. Create a JSON object with ONE key: "schedule".
            The "schedule" is an array of objects. Each object represents a DAY and must have:
            - "day": "Monday", "Tuesday", etc.
            - "breakfast": {{ "title": "Name", "ingredients": "Specific list with quantities (e.g. '2 Eggs', '1 cup Oats')", "instructions": "Steps" }}
            - "lunch": {{ "title": "Name", "ingredients": "Specific list with quantities (e.g. '4oz Chicken', '1 Avocado')", "instructions": "Steps" }}
            - "dinner": {{ "title": "Name", "ingredients": "Specific list with quantities (e.g. '1lb Beef', '1 cup Rice')", "instructions": "Steps" }}
            - "nutrition": {{ "calories": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 70 }}
            
            CRITICAL: You must list specific quantities (lbs, oz, cups, count) for every ingredient so the shopping list is accurate.
            """),
            ("human", "{input}")
        ])
        
        chain = prompt | llm
        response = await chain.ainvoke({"input": state["messages"][-1].content})
        
        try:
            content = re.sub(r"^```json|```$", "", response.content.strip(), flags=re.MULTILINE).strip()
            json.loads(content) 
            plan_json_str = content
        except:
            plan_json_str = json.dumps({"schedule": []})
        
        status.write("Plan created.")
    return {"meal_plan_json": plan_json_str, "total_cost": 0.0}

async def extractor_node(state: AgentState):
    with st.status("📑 Extractor: Building Shopping List...", expanded=True) as status:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY"))
        
        past_buys = db.get_all_past_items()
        # Shopping List Extractor Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a rigorous shopping list compiler.
            1. Read the provided JSON meal plan.
            2. Extract the 'ingredients' string from EVERY meal.
            3. Consolidate items by summing up quantities where possible (e.g., "2 eggs" + "2 eggs" = "4 Eggs").
            4. Compare against PANTRY: {pantry}. Remove any matches.
            5. Check HISTORY below. If a generic item (e.g. "Peanut Butter") matches a brand in history (e.g. "Smuckers"), use the specific one.
            6. STRICT OUTPUT RULE: Return ONLY a comma-separated list of items. Do not speak. Do not add introduction text.
            
            HISTORY: {history}
            """),
            ("human", "{input}")
        ])
        
        response = await (prompt | llm).ainvoke({
            "input": state["meal_plan_json"], 
            "pantry": state.get("pantry_items", ""),
            "history": past_buys
        })
        
        raw_list = response.content.split(',')
        items = []
        for i in raw_list:
            clean = re.sub(r'\s+', ' ', i).strip()
            if clean: items.append(clean)
            
        status.write(f"Identified {len(items)} items.")
    return {"shopping_list": items}

async def shopper_node(state: AgentState):
    shopping_list = state["shopping_list"]
    current_total = state.get("total_cost", 0.0)
    limit = state.get("budget_limit", 200.0)
    cart, missing = [], []
    # Gemini Flash for shopping
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY"))
    browser_tool = st.session_state.browser_tool
    
    status_container = st.status("🛒 Shopper: Smart Search Active...", expanded=True)
    if not browser_tool.page: await browser_tool.start()
    progress_bar = status_container.progress(0)
    
    for i, item in enumerate(shopping_list):
        status_container.write(f"Looking for: **{item}**")
        if current_total >= limit:
            missing.append(f"{item} (Budget Cut)")
            continue
        
        options = await browser_tool.search_and_get_options(item)
        
        if not options:
            missing.append(item)
            continue
            
        choice_prompt = f"User wants '{item}'. Options:\n"
        for opt in options: choice_prompt += f"Index {opt['index']}: {opt['title']} - ${opt['price_str']}\n"
        choice_prompt += "Return ONLY the Index integer (0, 1, or 2) of the best match/value."
        
        decision_msg = await llm.ainvoke([HumanMessage(content=choice_prompt)])
        try: choice_idx = int(re.search(r'-?\d+', decision_msg.content).group())
        except: choice_idx = 0
            
        if choice_idx >= 0 and choice_idx < len(options):
            chosen = options[choice_idx]
            success = await browser_tool.add_specific_item(choice_idx)
            if success:
                cart.append(f"{chosen['title']} (${chosen['price_str']})")
                current_total += chosen['price']
            else:
                st.toast(f"Smart add failed for {item}. Retrying...")
                bf_result = await browser_tool.search_and_add(item)
                if bf_result["status"] == "ADDED":
                    cart.append(f"{item} (${bf_result['price']:.2f})")
                    current_total += bf_result["price"]
                else:
                    missing.append(item)
        else:
            missing.append(f"{item} (No good match)")
            
        progress_bar.progress((i + 1) / len(shopping_list))

    status_container.write("🚚 Initializing Checkout...")
    await browser_tool.trigger_checkout()
    status_container.update(label="Shopping Done. Handoff Initiated.", state="complete", expanded=False)
    return {"cart_items": cart, "missing_items": missing, "total_cost": current_total}

async def human_review_node(state: AgentState): return state
async def checkout_node(state: AgentState): return {"messages": [SystemMessage(content="Handoff.")]}

# ==========================================
# 5. STREAMLIT UI
# ==========================================

st.set_page_config(page_title="Amazon Fresh Fetch", page_icon="🥕", layout="wide")

st.markdown("""
<style>
    .meal-card {
        background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px;
        padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 8px solid #ff4b4b; height: 100%;
    }
    .meal-header { font-size: 1.2rem; font-weight: 700; color: #1f1f1f; margin-bottom: 8px; display: flex; align-items: center; }
    .meal-body { font-size: 1rem; color: #4f4f4f; line-height: 1.5; }
    .icon { margin-right: 8px; }
</style>
""", unsafe_allow_html=True)

# INIT GRAPH
if 'graph_app' not in st.session_state:
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
    st.session_state.graph_app = workflow.compile(checkpointer=MemorySaver(), interrupt_before=["shopper", "checkout"])
    st.session_state.browser_tool = AmazonFreshBrowser()

app = st.session_state.graph_app

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Settings")
    budget = st.number_input("Weekly Budget ($)", value=float(db.get_setting("budget", "200.0")), step=10.0)
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
        st.session_state.pop('history_view', None)
        st.rerun()

    past_plans = db.get_recent_plans()
    for p in past_plans:
        if st.button(f"{p['date']} - {len(p['list'])} items", key=f"hist_{p['id']}"):
            st.session_state.history_view = p
            st.rerun()

st.title("🥕 Amazon Fresh Fetch AI Agent")

# --- WEEKLY MEAL PLAN PROMPT ---
default_prompt = """You are a world-class nutritionist and meal planning expert. Create a tailored Monday-Friday meal plan (Breakfast, Lunch, Dinner) for 2 adults.

**CORE CONSTRAINTS:**
- **Dietary:** No Pork. Heart-healthy. Focus on whole grains and fresh produce.
- **Nutrition:** Aim for ~30g protein per meal. Avoid sugar crashes (low glycemic index).
- **Time:** Meals must be on the table in 30 mins or less (except 1 "long cook" meal allowed).
- **Budget:** Mix premium cuts with budget-friendly staples.

**MEAL CADENCE:**
- **Dinner:** Cook fresh 3 nights a week.
- **Lunch:** Use leftovers from dinner for most lunches. On non-leftover days, schedule quick sandwiches/wraps/salads.
- **Breakfast:** Rotate between: Yogurt with whole grain toast, English muffins (PB/Jam/Avocado/Cheese), Eggs, or healthy Muffins.

**PREFERENCES:**
- **Cuisines:** Mexican, Mediterranean, Stir-fries.
- **Cooking Style:** Sheet pan, One-pot, Grilling, Slow Cooker.
- **Appliances Available:** Instant Pot, Rice Cooker.
- **Protein Variety:** Chicken, Beef, Seafood (Tilapia, Salmon, Cod, Shrimp), Lamb.
- **Vegetarian:** Include 1-2 vegetarian dinners per week.
- **Red Meat Limit:** Maximum 1-2 times per week.

**OUTPUT FORMAT:**
Return a VALID JSON object with exactly one key: "schedule".
"""

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit_run_final"

user_prompt = st.text_area("Meal Prompt", value=default_prompt, height=200)

if st.button("📝 Generate Plan", type="primary"):
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "budget_limit": budget,
        "pantry_items": pantry,
        "total_cost": 0.0
    }
    async def run_to_planning():
        async for event in app.astream(initial_state, config): pass
    asyncio.run(run_to_planning())
    st.rerun()

# STATE HANDLING
config = {"configurable": {"thread_id": st.session_state.thread_id}}
try:
    snapshot = app.get_state(config)
    current_step = snapshot.next[0] if snapshot.next else None
except: current_step = None

# --- HELPER TO RENDER PLAN ---
def render_plan_ui(plan_json):
    try:
        plan_data = json.loads(plan_json)
        schedule = plan_data.get('schedule', [])
        if schedule:
            nutri_data = []
            for day in schedule:
                n = day.get('nutrition', {})
                nutri_data.append({
                    "Day": day['day'], "Calories": n.get('calories', 0),
                    "Protein": n.get('protein_g', 0), "Carbs": n.get('carbs_g', 0), "Fat": n.get('fat_g', 0)
                })
            if nutri_data:
                df_nutri = pd.DataFrame(nutri_data)
                st.subheader("📊 Nutritional Analysis")
                c1, c2 = st.columns(2)
                with c1: st.bar_chart(df_nutri.set_index("Day")["Calories"], color="#ff4b4b")
                with c2: st.bar_chart(df_nutri.set_index("Day")[["Protein", "Carbs", "Fat"]])

            st.subheader("📅 Weekly Plan")
            tabs = st.tabs([day['day'] for day in schedule])
            for tab, day_info in zip(tabs, schedule):
                with tab:
                    c1, c2, c3 = st.columns(3)
                    def get_title(m): return m.get('title', str(m)) if isinstance(m, dict) else str(m)
                    with c1:
                        st.markdown(f"""<div class="meal-card"><div class="meal-header"><span class="icon">🥞</span> Breakfast</div><div class="meal-body">{get_title(day_info.get('breakfast'))}</div></div>""", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""<div class="meal-card"><div class="meal-header"><span class="icon">🥗</span> Lunch</div><div class="meal-body">{get_title(day_info.get('lunch'))}</div></div>""", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"""<div class="meal-card"><div class="meal-header"><span class="icon">🍳</span> Dinner</div><div class="meal-body">{get_title(day_info.get('dinner'))}</div></div>""", unsafe_allow_html=True)
                    
                    with st.expander("👨‍🍳 View Cooking Instructions"):
                        st.json(day_info)
    except Exception as e:
        st.error(f"Error rendering plan: {e}")

# --- CHECK VIEW MODE (HISTORY vs NEW) ---
if 'history_view' in st.session_state:
    h_data = st.session_state.history_view
    st.info(f"📂 Viewing Past Plan from: **{h_data['date']}**")
    if st.button("⬅️ Back to New Plan"):
        del st.session_state.history_view
        st.rerun()
    render_plan_ui(h_data['json'])
    st.divider()
    st.subheader("🛒 Historic Shopping List")
    st.dataframe(h_data['list'])

# --- REVIEW PHASE (NEW PLAN) ---
elif current_step == "shopper":
    st.divider()
    data = snapshot.values
    render_plan_ui(data['meal_plan_json'])

    st.divider()
    c_head, c_pdf = st.columns([3, 1])
    with c_head: st.subheader("🛒 Confirm Ingredients")
    
    raw_list = data.get('shopping_list', [])
    df = pd.DataFrame({"Item": raw_list, "Buy": [True]*len(raw_list)})
    
    edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")
    final_list = edited_df[edited_df["Buy"] == True]["Item"].tolist()

    with c_pdf:
        try:
            pdf_bytes = generate_pdf(data['meal_plan_json'], final_list)
            st.download_button(
                label="📄 Download PDF Plan",
                data=pdf_bytes,
                file_name="plan.pdf",
                mime="application/pdf",
                use_container_width=True 
            )
        except: st.error("PDF Error")
    
    if st.button(f"✅ Shop for {len(final_list)} Items", type="primary"):
        db.save_plan(user_prompt, data['meal_plan_json'], final_list)
        app.update_state(config, {"shopping_list": final_list})
        async def resume():
            async for event in app.astream(None, config): pass
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
    
    cart_c = len(data.get('cart_items', []))
    miss_c = len(data.get('missing_items', []))
    total = cart_c + miss_c
    rate = int((cart_c/total)*100) if total > 0 else 0
    c3.metric("Success Rate", f"{rate}%")

    col_a, col_b = st.columns(2)
    with col_a:
        st.success(f"✅ **Added ({cart_c})**")
        if cart_c > 0:
            st.dataframe(pd.DataFrame(data.get('cart_items', []), columns=["Item"]), width="stretch", hide_index=True)
        else: st.write("None.")

    with col_b:
        st.error(f"❌ **Missed ({miss_c})**")
        if miss_c > 0:
            st.warning("⚠️ Check these manually.")
            st.dataframe(pd.DataFrame(data.get('missing_items', []), columns=["Item"]), width="stretch", hide_index=True)
        else: st.write("None.")

    st.divider()
    st.info("👋 **Manual Handoff:** Please complete payment in the open browser window.")
    if st.button("Close"): asyncio.run(st.session_state.browser_tool.close())