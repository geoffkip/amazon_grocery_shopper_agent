import os
import asyncio
import json
import re
from dotenv import load_dotenv

# Load environment variables (API Key)
load_dotenv()

from typing import List, Optional, TypedDict, Annotated
from operator import add

# LangChain / LangGraph imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Browser Automation imports
from playwright.async_api import async_playwright

# --- 1. State Definition ---
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

# --- 2. The Browser Tool (Auto-Login & Budget Logic) ---
class AmazonFreshBrowser:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.session_file = "amazon_session.json"

    async def start(self):
        print("🚀 Launching Browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False, slow_mo=1500)
        
        # Try to load saved session
        if os.path.exists(self.session_file):
            print(f"🍪 Found saved session. Attempting auto-login...")
            self.context = await self.browser.new_context(
                storage_state=self.session_file,
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        else:
            print("🆕 No session found. Starting fresh.")
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        self.page = await self.context.new_page()
        await self.page.goto("https://www.amazon.com/alm/storefront?almBrandId=QW1hem9uIEZyZXNo")
        
        # Check if login is needed
        try:
            needs_login = await self.page.locator("#nav-link-accountList-nav-line-1").filter(has_text="Sign in").count() > 0
        except:
            needs_login = True

        if needs_login:
            print("\n⚠️  ACTION REQUIRED: Please Log In manually within 60 seconds.")
            await asyncio.sleep(60)
            print("💾 Saving session for next time...")
            await self.context.storage_state(path=self.session_file)
        else:
            print("✅ Auto-login successful!")

    async def search_and_add(self, item_name: str) -> dict:
        try:
            print(f"🛒 Searching for: {item_name}")
            search_box = self.page.locator('input[id="twotabsearchtextbox"]')
            await search_box.clear()
            await search_box.fill(item_name)
            await search_box.press('Enter')
            
            try:
                await self.page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=5000)
            except:
                print("  - Standard search results not found...")

            first_result = self.page.locator('div[data-component-type="s-search-result"]').first
            if await first_result.count() == 0:
                return {"status": "NOT_FOUND", "price": 0.0}

            # Extract Price
            price = 0.0
            try:
                price_element = first_result.locator(".a-price .a-offscreen").first
                if await price_element.count() > 0:
                    price_text = await price_element.text_content()
                    clean_price = price_text.replace("$", "").replace(",", "").strip()
                    price = float(clean_price)
                    print(f"  💲 Price detected: ${price}")
            except Exception as e:
                print(f"  ⚠️ Could not read price: {e}")

            # Add to Cart
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
            return {"status": f"ERROR: {e}", "price": 0.0}

    async def close(self):
        if self.context:
            await self.context.storage_state(path=self.session_file)
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()

browser_tool = AmazonFreshBrowser()

# --- 3. Nodes (Gemini 2.5 Pro) ---

async def planner_node(state: AgentState):
    print("\n🧠 Thinking... Analyzing request with Gemini 2.5 Pro...")
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY"))
    user_prompt = state["messages"][-1].content
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Analyze the user request. Return JSON with 'plan' and 'delivery_preference' keys."),
        ("human", "{input}")
    ])
    
    chain = prompt | llm
    response = await chain.ainvoke({"input": user_prompt})
    
    try:
        content = re.sub(r"^```json|```$", "", response.content.strip(), flags=re.MULTILINE).strip()
        data = json.loads(content)
        plan_text = data.get("plan", "Error")
        del_window = data.get("delivery_preference", "Not specified")
    except:
        plan_text = response.content
        del_window = "Not specified"

    print("\n📝 PLAN GENERATED (Snippet):")
    print(plan_text[:200] + "...")
    print(f"🚚 Delivery Preference: {del_window}")

    return {
        "meal_plan_text": plan_text,
        "delivery_window": del_window,
        "total_cost": 0.0,
    }

async def extractor_node(state: AgentState):
    print("\n📑 Extracting grocery list (Checking Pantry)...")
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY"))
    pantry = state.get("pantry_items", "Nothing")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a smart shopping assistant.\n"
                   "1. Read the meal plan.\n"
                   "2. Compare it against the user's PANTRY STOCK: {pantry_stock}.\n"
                   "3. RULE: If an ingredient is in the pantry stock, DO NOT add it to the list.\n"
                   "4. Be SPECIFIC with items (e.g., 'Hass Avocado Single' not just 'Avocado').\n"
                   "5. Return ONLY a comma-separated list of items to buy."),
        ("human", "{input}")
    ])
    
    chain = prompt | llm
    response = await chain.ainvoke({
        "input": state["meal_plan_text"], 
        "pantry_stock": pantry
    })
    
    items = [item.strip() for item in response.content.split(',')]
    print(f"🛒 Extracted {len(items)} items to buy (after filtering pantry).")
    return {"shopping_list": items}

async def shopper_node(state: AgentState):
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.2, google_api_key=os.getenv("GOOGLE_API_KEY"))
    shopping_list = state["shopping_list"]
    current_total = state.get("total_cost", 0.0)
    limit = state.get("budget_limit", 200.0)

    cart, missing = [], []
    print(f"\n💰 STARTING SHOPPING RUN. Budget: ${limit:.2f}")

    if not browser_tool.page: await browser_tool.start()

    for item in shopping_list:
        # Budget Check
        if current_total >= limit:
            print(f"🛑 BUDGET HIT. Skipping {item}.")
            missing.append(f"{item} (SKIPPED - BUDGET)")
            continue

        result = await browser_tool.search_and_add(item)
        
        if result["status"] == "ADDED":
            cart.append(f"{item} (${result['price']:.2f})")
            current_total += result["price"]
            print(f"   📈 Total: ${current_total:.2f}")
        elif "NOT_FOUND" in result["status"]:
            print(f"⚠️ {item} missing. Finding sub...")
            sub_resp = await llm.ainvoke([HumanMessage(content=f"Item '{item}' unavailable. Name ONE generic substitute.")])
            sub_item = sub_resp.content.strip()
            
            retry = await browser_tool.search_and_add(sub_item)
            if retry["status"] == "ADDED":
                cart.append(f"{sub_item} (Sub) - ${retry['price']:.2f}")
                current_total += retry['price']
            else:
                missing.append(item)
        else:
            missing.append(f"{item} (Error)")

    return {"cart_items": cart, "missing_items": missing, "total_cost": current_total}

async def human_review_node(state: AgentState):
    print("\n" + "="*30 + "\n🛑 HUMAN REVIEW REQUIRED\n" + "="*30)
    print(f"💰 Total Estimated Cost: ${state['total_cost']:.2f}")
    print(f"📉 Budget Limit: ${state['budget_limit']:.2f}")
    print(f"\n🛒 Cart Items ({len(state['cart_items'])}):")
    for i in state['cart_items']: print(f" - {i}")
    return state

async def checkout_node(state: AgentState):
    if not state.get("user_approved"): return {"messages": [SystemMessage(content="Aborted.")]}
    window = state.get("delivery_window", "Not specified")
    return {"messages": [SystemMessage(content=f"Done. Delivery: {window}")]}

# --- 4. Graph Construction ---
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

app = workflow.compile(checkpointer=MemorySaver(), interrupt_before=["checkout"])

# --- 5. Execution ---
async def main():
    # The Meal Planning Prompt
    default_prompt = """You are a meal planning expert. Help me build a weekly meal plan for dinner and lunch- I need healthy meals on the table in 30 minutes or less. I’d like it to be a full Monday-Friday meal plan with the links to the recipes and a grocery list included. I’m feeding 2 people, 2 adults. We don't eat pork. I’m accommodating no other allergens or restrictions and try to have a balanced diet focusing that incorporates a variety of whole grains. I'd like it to be heart healthy. I include protein and fresh produce at every meal. We enjoy global flavors like Mexican, Mediterranean, stir fries. I aim for 30 grams of protein at every meal. We usually cook 3 nights a week and use leftovers for lunch or other dinner. One or two lunches can be a sandwich/wrap or salad (something quick as for lunch I typically don't have time. For one meal a week it can be a bit of a longer cooking time. My preferred cooking styles are sheet pan or one saute pan, slow cooker and grilling. I own an Instant Pot and a rice cooker. We would prefer 1-2 vegetarian meals per week. We try to limit red meat to about 1-2 times a week. We eat all other animal products including beef, chicken, tilapia, salmon, cod, shrimp and lamb. Please have the plan include a variety of proteins - so one night chicken, one night beef. We want to include premium cuts while also incorporating budget-friendly staples and limiting specialty ingredients. My preferred grocery stores are amazon fresh, also, food lion, harris teeters and Wegmans. I'd also like you to include breakfast - we typically eat yogurt with whole grain toast or English muffins with peanut butter, jam, avocado and cheese. Some days we also make eggs and some days I sometimes make muffins. Feel free to suggest other healthy breakfast options. Avoiding sugar crashes is also important to me."""
    
    print("\n" + "="*60)
    print("🥕 AMAZON FRESH AGENT (Full Feature Set)")
    print("="*60)
    
    # 1. Prompt Selection
    print("Enter meal request OR press [ENTER] for the default detailed prompt.")
    user_input = input("> ")
    final_prompt = user_input if user_input.strip() else default_prompt
    
    # 2. Budget
    print("\nWhat is your max weekly budget? (Press Enter for $200)")
    budget_in = input("> $")
    try: budget_limit = float(budget_in) if budget_in.strip() else 200.0
    except: budget_limit = 200.0

    # 3. Pantry
    print("\nWhat items do you ALREADY have in stock?")
    print("(e.g., 'chicken, rice, salt, eggs'. Press Enter if nothing.)")
    pantry_in = input("> ")
    final_pantry = pantry_in if pantry_in.strip() else "Nothing"

    initial_state = {
        "messages": [HumanMessage(content=final_prompt)],
        "budget_limit": budget_limit,
        "pantry_items": final_pantry,
        "total_cost": 0.0
    }

    config = {"configurable": {"thread_id": "full_feature_run_v2"}}
    async for event in app.astream(initial_state, config): pass

    state = app.get_state(config)
    if state.next and state.next[0] == 'checkout':
        decision = input("\nProceed to checkout? (yes/no): ").lower()
        if decision == 'yes':
            app.update_state(config, {"user_approved": True})
            async for event in app.astream(None, config): pass

    await browser_tool.close()

if __name__ == "__main__":
    asyncio.run(main())