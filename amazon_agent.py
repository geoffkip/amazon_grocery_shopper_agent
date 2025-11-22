import streamlit as st
import os
import asyncio
import json
import re
import pandas as pd
from dotenv import load_dotenv
from typing import List, TypedDict, Annotated
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
# 1. SETUP & CLASSES
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
        self.browser = await self.playwright.chromium.launch(headless=False, slow_mo=1500)
        
        if os.path.exists(self.session_file):
            self.context = await self.browser.new_context(
                storage_state=self.session_file,
                viewport={"width": 1280, "height": 720}
            )
            st.toast("🍪 Session loaded")
        else:
            self.context = await self.browser.new_context(viewport={"width": 1280, "height": 720})

        self.page = await self.context.new_page()
        await self.page.goto("https://www.amazon.com/alm/storefront?almBrandId=QW1hem9uIEZyZXNo")
        
        try:
            needs_login = await self.page.locator("#nav-link-accountList-nav-line-1").filter(has_text="Sign in").count() > 0
        except:
            needs_login = True

        if needs_login:
            st.warning("⚠️ Please Log In manually in the browser window!")
            await asyncio.sleep(60)
            await self.context.storage_state(path=self.session_file)
        else:
            st.success("✅ Verified Logged In")

    async def search_and_add(self, item_name: str) -> dict:
        try:
            search_box = self.page.locator('input[id="twotabsearchtextbox"]')
            await search_box.clear()
            await search_box.fill(item_name)
            await search_box.press('Enter')
            try: await self.page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=5000)
            except: pass

            first_result = self.page.locator('div[data-component-type="s-search-result"]').first
            if await first_result.count() == 0: return {"status": "NOT_FOUND", "price": 0.0}

            price = 0.0
            try:
                price_element = first_result.locator(".a-price .a-offscreen").first
                if await price_element.count() > 0:
                    txt = await price_element.text_content()
                    price = float(txt.replace("$", "").replace(",", "").strip())
            except: pass

            btn = first_result.get_by_role("button", name="Add to cart")
            if await btn.count() == 0: btn = first_result.get_by_role("button", name="Add", exact=True)
            if await btn.count() == 0: btn = first_result.locator("button[name='submit.addToCart']")
            if await btn.count() == 0: btn = first_result.locator("input[name='submit.addToCart']")

            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                await asyncio.sleep(2)
                return {"status": "ADDED", "price": price}
            
            return {"status": "NOT_FOUND", "price": 0.0}
        except Exception as e:
            return {"status": f"ERROR", "price": 0.0}

    async def trigger_checkout(self):
        """
        Navigates to cart and clicks the initial checkout button.
        """
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
                
        except Exception as e:
            st.error(f"Could not click checkout: {e}")
            return False
            
        return False

    async def close(self):
        if self.context: await self.context.storage_state(path=self.session_file)
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

# ==========================================
# 2. PDF GENERATOR CLASS
# ==========================================

class MealPlanPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Amazon Fresh Fetch - Weekly Meal Plan', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def clean_text(self, text):
        if not text: return ""
        return text.encode('latin-1', 'replace').decode('latin-1')

def generate_pdf(meal_json_str: str, shopping_list: List[str]) -> bytes:
    pdf = MealPlanPDF()
    pdf.add_page()
    
    # Shopping List
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Master Shopping List', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    
    col_width = 90
    for i in range(0, len(shopping_list), 2):
        item1 = shopping_list[i]
        item2 = shopping_list[i+1] if i+1 < len(shopping_list) else ""
        pdf.cell(col_width, 7, f"[ ] {pdf.clean_text(item1)}", 0, 0)
        if item2:
            pdf.cell(col_width, 7, f"[ ] {pdf.clean_text(item2)}", 0, 1)
        else:
            pdf.ln(7)
    
    pdf.ln(10)

    # Recipes
    try:
        data = json.loads(meal_json_str)
        schedule = data.get("schedule", [])
        
        for day in schedule:
            pdf.add_page()
            pdf.set_font('Arial', 'B', 20)
            pdf.set_text_color(255, 75, 75)
            pdf.cell(0, 15, pdf.clean_text(day['day']), 0, 1, 'L')
            pdf.set_text_color(0, 0, 0)
            
            for meal_type in ['breakfast', 'lunch', 'dinner']:
                meal_data = day.get(meal_type)
                if isinstance(meal_data, dict):
                    pdf.set_font('Arial', 'B', 14)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(0, 10, f"{meal_type.title()}: {pdf.clean_text(meal_data.get('title', ''))}", 0, 1, 'L', fill=True)
                    
                    pdf.set_font('Arial', 'I', 10)
                    pdf.multi_cell(0, 5, f"Ingredients: {pdf.clean_text(meal_data.get('ingredients', ''))}")
                    pdf.ln(2)
                    
                    pdf.set_font('Arial', '', 11)
                    pdf.multi_cell(0, 6, pdf.clean_text(meal_data.get('instructions', '')))
                    pdf.ln(8)
                else:
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, f"{meal_type.title()}: {pdf.clean_text(str(meal_data))}", 0, 1)

    except Exception as e:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"Error parsing recipe data: {str(e)}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. DEFINE NODES
# ==========================================

async def planner_node(state: AgentState):
    with st.status("🧠 Planner: Designing Schedule...", expanded=True) as status:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=1.0, google_api_key=os.getenv("GOOGLE_API_KEY"))
        
        # --- CLEANED PROMPT (No Delivery Window request) ---
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional chef and nutritionist. 
            Create a JSON object with exactly ONE key: "schedule".
            The "schedule" is an array of objects. Each object represents a DAY and must have:
            - "day": "Monday", "Tuesday", etc.
            - "breakfast": {{ "title": "Name", "ingredients": "List of items", "instructions": "Step-by-step cooking guide" }}
            - "lunch": {{ "title": "Name", "ingredients": "List of items", "instructions": "Step-by-step cooking guide" }}
            - "dinner": {{ "title": "Name", "ingredients": "List of items", "instructions": "Step-by-step cooking guide" }}
            
            Ensure the instructions are concise but actionable.
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
        
        status.write("Plan & Recipes created.")
    
    return {"meal_plan_json": plan_json_str, "total_cost": 0.0}

async def extractor_node(state: AgentState):
    with st.status("📑 Extractor: Building Shopping List...", expanded=True) as status:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY"))
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Read the meal plan JSON. Compare against PANTRY: {pantry}. Return SPECIFIC comma-separated list of ingredients needed for all meals."),
            ("human", "{input}")
        ])
        chain = prompt | llm
        response = await chain.ainvoke({
            "input": state["meal_plan_json"], 
            "pantry": state.get("pantry_items", "")
        })
        items = [i.strip() for i in response.content.split(',')]
        status.write(f"Identified {len(items)} items.")
    return {"shopping_list": items}

async def shopper_node(state: AgentState):
    shopping_list = state["shopping_list"]
    current_total = state.get("total_cost", 0.0)
    limit = state.get("budget_limit", 200.0)
    cart, missing = [], []
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.2, google_api_key=os.getenv("GOOGLE_API_KEY"))
    browser_tool = st.session_state.browser_tool
    status_container = st.status("🛒 Shopper: Searching Amazon Fresh...", expanded=True)
    if not browser_tool.page: await browser_tool.start()
    progress_bar = status_container.progress(0)
    
    for i, item in enumerate(shopping_list):
        status_container.write(f"Looking for: **{item}**")
        if current_total >= limit:
            missing.append(f"{item} (Budget Cut)")
            continue
        result = await browser_tool.search_and_add(item)
        if result["status"] == "ADDED":
            cart.append(f"{item} (${result['price']:.2f})")
            current_total += result["price"]
        elif "NOT_FOUND" in result["status"]:
            sub_resp = await llm.ainvoke([HumanMessage(content=f"Item '{item}' unavailable. Name ONE generic substitute.")])
            sub_item = sub_resp.content.strip()
            retry = await browser_tool.search_and_add(sub_item)
            if retry["status"] == "ADDED":
                cart.append(f"{sub_item} (Sub) - ${retry['price']:.2f}")
                current_total += retry['price']
            else:
                missing.append(item)
        else:
            missing.append(item)
        progress_bar.progress((i + 1) / len(shopping_list))

    status_container.write("🚚 Initializing Checkout...")
    await browser_tool.trigger_checkout()
    
    status_container.update(label="Shopping Done. Handoff Initiated.", state="complete", expanded=False)
    return {"cart_items": cart, "missing_items": missing, "total_cost": current_total}

async def human_review_node(state: AgentState):
    return state

async def checkout_node(state: AgentState):
    return {"messages": [SystemMessage(content="Checkout Handoff Complete.")]}

# ==========================================
# 4. GRAPH INIT
# ==========================================

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

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory, interrupt_before=["shopper", "checkout"])
    
    st.session_state.graph_app = app
    st.session_state.browser_tool = AmazonFreshBrowser()

app = st.session_state.graph_app
browser_tool = st.session_state.browser_tool

# ==========================================
# 5. STREAMLIT UI
# ==========================================

st.set_page_config(page_title="Amazon Fresh Fetch AI Agent", page_icon="🥕", layout="wide")

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

with st.sidebar:
    st.header("⚙️ Settings")
    budget = st.number_input("Weekly Budget ($)", value=200.0, step=10.0)
    # --- EMPTY PANTRY DEFAULT ---
    pantry = st.text_area("In Your Pantry", "")
    st.divider()
    if st.button("Reset Session"):
        st.session_state.clear()
        st.rerun()

st.title("🥕 Amazon Fresh Fetch AI Agent")

default_prompt = """You are a world-class nutritionist and meal planning expert. Create a tailored Monday-Friday meal plan (Breakfast, Lunch, Dinner) for 2 adults.

**CORE CONSTRAINTS:**
- **Dietary:** No Pork. Heart-healthy. Focus on whole grains and fresh produce.
- **Nutrition:** Aim for ~30g protein per meal. Avoid sugar crashes.
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
"""

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit_run_v19"

user_prompt = st.text_area("Meal Prompt", value=default_prompt, height=150)

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

config = {"configurable": {"thread_id": st.session_state.thread_id}}
try:
    snapshot = app.get_state(config)
    current_step = snapshot.next[0] if snapshot.next else None
except: current_step = None

# === STEP 1: PLAN REVIEW ===
if current_step == "shopper":
    st.divider()
    st.subheader("📅 Weekly Plan & Shopping List")
    
    data = snapshot.values
    
    try:
        plan_data = json.loads(data['meal_plan_json'])
        schedule = plan_data.get('schedule', [])
        if schedule:
            tabs = st.tabs([day['day'] for day in schedule])
            for tab, day_info in zip(tabs, schedule):
                with tab:
                    col_a, col_b, col_c = st.columns(3)
                    def get_meal_display(meal_data):
                        if isinstance(meal_data, dict): return meal_data.get('title', 'No Title')
                        return str(meal_data)

                    with col_a:
                        st.markdown(f"""<div class="meal-card"><div class="meal-header"><span class="icon">🥞</span> Breakfast</div><div class="meal-body">{get_meal_display(day_info.get('breakfast'))}</div></div>""", unsafe_allow_html=True)
                    with col_b:
                        st.markdown(f"""<div class="meal-card"><div class="meal-header"><span class="icon">🥗</span> Lunch</div><div class="meal-body">{get_meal_display(day_info.get('lunch'))}</div></div>""", unsafe_allow_html=True)
                    with col_c:
                        st.markdown(f"""<div class="meal-card"><div class="meal-header"><span class="icon">🍳</span> Dinner</div><div class="meal-body">{get_meal_display(day_info.get('dinner'))}</div></div>""", unsafe_allow_html=True)
                    
                    with st.expander("👨‍🍳 View Instructions"):
                        st.write(day_info)
    except Exception as e:
        st.error(f"Error displaying cards: {e}")

    st.divider()
    col_header, col_dl = st.columns([3, 1])
    with col_header: st.subheader("🛒 Confirm Ingredients")
    
    raw_list = data.get('shopping_list', [])
    if not raw_list: raw_list = []
    df = pd.DataFrame({"Item": raw_list, "Buy": [True]*len(raw_list)})
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, column_config={"Buy": st.column_config.CheckboxColumn("Buy?", default=True)})
    final_shopping_list = edited_df[edited_df["Buy"] == True]["Item"].tolist()

    with col_dl:
        try:
            pdf_bytes = generate_pdf(data['meal_plan_json'], final_shopping_list)
            st.download_button(
                label="📄 Download PDF Plan",
                data=pdf_bytes,
                file_name="fresh_fetch_plan.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error("PDF Gen Failed")

    if st.button(f"✅ Shop for {len(final_shopping_list)} Items", type="primary"):
        app.update_state(config, {"shopping_list": final_shopping_list})
        async def resume_shopping():
            async for event in app.astream(None, config): pass
        asyncio.run(resume_shopping())
        st.rerun()

# === STEP 2: CHECKOUT HANDOFF ===
elif current_step == "checkout":
    st.divider()
    st.subheader("🛑 Automation Complete")
    
    data = snapshot.values
    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated Cost", f"${data['total_cost']:.2f}")
    c2.metric("Budget", f"${data['budget_limit']:.2f}")
    c3.metric("Items in Cart", len(data.get('cart_items', [])))

    col_a, col_b = st.columns(2)
    with col_a:
        st.success("✅ In Cart")
        st.dataframe(data.get('cart_items', []), height=300)
    with col_b:
        st.error("❌ Missing/Skipped")
        st.dataframe(data.get('missing_items', []), height=300)

    st.write("---")
    st.info("👋 **Manual Handoff Required**")
    st.markdown("""
    ### ⚠️ Action Required in Browser
    1. The agent has filled your cart and clicked **"Check out Fresh Cart"**.
    2. Please switch to the opened Chrome window.
    3. You must manually complete:
        * **Upsells / Substitutions**
        * **Payment Method**
        * **Delivery Schedule**
        * **Final "Place Order"**
    """)
    
    if st.button("🛑 Close Browser & End Session"):
        asyncio.run(browser_tool.close())
        st.warning("Session Closed.")