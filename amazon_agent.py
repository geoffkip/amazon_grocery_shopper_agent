import streamlit as st
import os
import asyncio
import json
import re
import pandas as pd
from dotenv import load_dotenv
from typing import List, TypedDict, Annotated
from operator import add

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
    meal_plan_text: str
    shopping_list: List[str]
    cart_items: List[str]
    missing_items: List[str]
    user_approved: bool
    delivery_window: str
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
            
            try:
                await self.page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=5000)
            except: pass

            first_result = self.page.locator('div[data-component-type="s-search-result"]').first
            if await first_result.count() == 0:
                return {"status": "NOT_FOUND", "price": 0.0}

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

    async def close(self):
        if self.context: await self.context.storage_state(path=self.session_file)
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

# ==========================================
# 2. DEFINE NODES
# ==========================================

async def planner_node(state: AgentState):
    with st.status("🧠 Planner: Generating Menu...", expanded=True) as status:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY"))
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Analyze request. Return JSON with 'plan' and 'delivery_preference' keys."),
            ("human", "{input}")
        ])
        chain = prompt | llm
        response = await chain.ainvoke({"input": state["messages"][-1].content})
        
        try:
            content = re.sub(r"^```json|```$", "", response.content.strip(), flags=re.MULTILINE).strip()
            data = json.loads(content)
            plan_text = data.get("plan", "Error")
            del_window = data.get("delivery_preference", "Not specified")
        except:
            plan_text = response.content
            del_window = "Not specified"
        
        status.write("Plan created.")
    return {"meal_plan_text": plan_text, "delivery_window": del_window, "total_cost": 0.0}

async def extractor_node(state: AgentState):
    with st.status("📑 Extractor: Creating Shopping List...", expanded=True) as status:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY"))
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Read meal plan. Compare against PANTRY: {pantry}. "
                       "Return SPECIFIC comma-separated list of needed items. Exclude pantry items."),
            ("human", "{input}")
        ])
        chain = prompt | llm
        response = await chain.ainvoke({
            "input": state["meal_plan_text"], 
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

    # Access browser from session state
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
            status_container.write(f"⚠️ {item} missing. Substituting...")
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

    status_container.update(label="Shopping Complete!", state="complete", expanded=False)
    return {"cart_items": cart, "missing_items": missing, "total_cost": current_total}

async def human_review_node(state: AgentState):
    return state

async def checkout_node(state: AgentState):
    if not state.get("user_approved"): return {"messages": [SystemMessage(content="Aborted.")]}
    return {"messages": [SystemMessage(content=f"Checkout Complete.")]}

# ==========================================
# 3. INITIALIZE GRAPH (PERSISTENT)
# ==========================================

if 'graph_app' not in st.session_state:
    # We build the graph ONCE and store it in session state
    # This ensures the Checkpointer (Memory) survives Streamlit reruns
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

    # Create Checkpointer
    memory = MemorySaver()
    
    # Compile with interrupt
    app = workflow.compile(checkpointer=memory, interrupt_before=["shopper", "checkout"])
    
    st.session_state.graph_app = app
    st.session_state.browser_tool = AmazonFreshBrowser()

# Shortcuts for easier access
app = st.session_state.graph_app
browser_tool = st.session_state.browser_tool

# ==========================================
# 4. STREAMLIT UI
# ==========================================

st.set_page_config(page_title="Amazon Fresh Agent", page_icon="🥕", layout="wide")

with st.sidebar:
    st.header("⚙️ Settings")
    budget = st.number_input("Weekly Budget ($)", value=200.0, step=10.0)
    pantry = st.text_area("In Your Pantry", "Salt, Pepper, Olive Oil")
    st.divider()
    if st.button("Reset Session"):
        # Clear everything to restart fresh
        st.session_state.clear()
        st.rerun()

st.title("🥕 Amazon Fresh AI Agent")

# Default Prompt
default_prompt = """You are a meal planning expert. Help me build a weekly meal plan for dinner and lunch- I need healthy meals on the table in 30 minutes or less. I’d like it to be a full Monday-Friday meal plan with the links to the recipes and a grocery list included. I’m feeding 2 people, 2 adults. We don't eat pork. I’m accommodating no other allergens or restrictions and try to have a balanced diet focusing that incorporates a variety of whole grains. I'd like it to be heart healthy. I include protein and fresh produce at every meal. We enjoy global flavors like Mexican, Mediterranean, stir fries. I aim for 30 grams of protein at every meal. We usually cook 3 nights a week and use leftovers for lunch or other dinner. One or two lunches can be a sandwich/wrap or salad (something quick as for lunch I typically don't have time. For one meal a week it can be a bit of a longer cooking time. My preferred cooking styles are sheet pan or one saute pan, slow cooker and grilling. I own an Instant Pot and a rice cooker. We would prefer 1-2 vegetarian meals per week. We try to limit red meat to about 1-2 times a week. We eat all other animal products including beef, chicken, tilapia, salmon, cod, shrimp and lamb. Please have the plan include a variety of proteins - so one night chicken, one night beef. We want to include premium cuts while also incorporating budget-friendly staples and limiting specialty ingredients. My preferred grocery stores are amazon fresh, also, food lion, harris teeters and Wegmans. I'd also like you to include breakfast - we typically eat yogurt with whole grain toast or English muffins with peanut butter, jam, avocado and cheese. Some days we also make eggs and some days I sometimes make muffins. Feel free to suggest other healthy breakfast options. Avoiding sugar crashes is also important to me."""

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit_run_3"

# --- INPUT SECTION ---
user_prompt = st.text_area("Meal Prompt", value=default_prompt, height=200)

col1, col2 = st.columns([1, 4])
with col1:
    start_btn = st.button("📝 Generate Plan", type="primary")

if start_btn:
    # Start fresh logic
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    initial_state = {
        "messages": [HumanMessage(content=user_prompt)],
        "budget_limit": budget,
        "pantry_items": pantry,
        "total_cost": 0.0
    }
    
    async def run_to_planning():
        # Running streaming execution
        async for event in app.astream(initial_state, config): pass
            
    asyncio.run(run_to_planning())
    st.rerun()

# --- STATE INSPECTION & LOGIC ---
config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Try to fetch current state
try:
    snapshot = app.get_state(config)
    current_step = snapshot.next[0] if snapshot.next else None
except:
    current_step = None

# === UI STATE 1: REVIEW PLAN & LIST ===
if current_step == "shopper":
    st.divider()
    st.subheader("👀 Review Your Plan & List")
    
    data = snapshot.values
    
    # 1. Editable Meal Plan
    st.caption("You can edit the plan text below if you want to change meals.")
    edited_plan = st.text_area("Meal Plan", value=data['meal_plan_text'], height=300)
    
    # 2. Editable Shopping List
    st.caption("Review ingredients. Uncheck items you don't need or add new ones.")
    
    # Convert list to DataFrame for editing
    raw_list = data.get('shopping_list', [])
    if not raw_list: raw_list = []
    
    df = pd.DataFrame({"Item": raw_list, "Buy": [True]*len(raw_list)})
    
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={"Buy": st.column_config.CheckboxColumn("Buy?", default=True)}
    )
    
    # Filter only checked items
    final_shopping_list = edited_df[edited_df["Buy"] == True]["Item"].tolist()

    st.info(f"Ready to shop for **{len(final_shopping_list)}** items.")

    if st.button("✅ Confirm Plan & Start Shopping", type="primary"):
        # Update state with user edits
        app.update_state(config, {
            "meal_plan_text": edited_plan,
            "shopping_list": final_shopping_list
        })
        
        async def resume_shopping():
            # Resume graph execution (Pass None to continue from pause)
            async for event in app.astream(None, config): pass
        
        asyncio.run(resume_shopping())
        st.rerun()

# === UI STATE 2: CHECKOUT REVIEW ===
elif current_step == "checkout":
    st.divider()
    st.subheader("🛑 Final Checkout Review")
    
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

    del_window = data.get("delivery_window", "Not specified")
    st.write(f"**Detected Delivery:** {del_window}")
    new_window = st.text_input("Confirm/Update Delivery Window:", value=del_window)

    b1, b2 = st.columns(2)
    if b1.button("✅ Place Order"):
        app.update_state(config, {"user_approved": True, "delivery_window": new_window})
        
        async def finish_checkout():
            async for event in app.astream(None, config): pass
        
        asyncio.run(finish_checkout())
        st.success(f"Order Process Complete! Delivery set for {new_window}.")
        st.balloons()
        
    if b2.button("🛑 Cancel"):
        st.warning("Cancelled.")
        asyncio.run(browser_tool.close())