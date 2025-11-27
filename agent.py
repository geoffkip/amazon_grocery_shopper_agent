"""
Agent logic and LangGraph nodes for Amazon Fresh Agent.

This module defines the state and the nodes for the LangGraph workflow, including
planning, extracting ingredients, and shopping.
"""

import json
import os
import re
from operator import add
from typing import Annotated, List, TypedDict

import streamlit as st
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from config import EXTRACTOR_MODEL, PLANNER_MODEL, SHOPPER_MODEL
from database import db
from prompts import EXTRACTOR_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT


class AgentState(TypedDict):
    """
    State definition for the agent workflow.

    Attributes:
        messages (List[BaseMessage]): Chat history.
        meal_plan_json (str): Generated meal plan in JSON format.
        shopping_list (List[str]): List of ingredients to buy.
        cart_items (List[str]): Items successfully added to the cart.
        missing_items (List[str]): Items that could not be found or added.
        user_approved (bool): Whether the user approved the plan.
        total_cost (float): Total cost of items in the cart.
        budget_limit (float): User-defined budget limit.
        pantry_items (str): User's pantry items to exclude.
    """

    messages: Annotated[List[BaseMessage], add]
    meal_plan_json: str
    shopping_list: List[str]
    cart_items: List[str]
    missing_items: List[str]
    user_approved: bool
    total_cost: float
    budget_limit: float
    pantry_items: str


async def planner_node(state: AgentState):
    """
    Generate a weekly meal plan based on user input.

    Args:
        state (AgentState): The current agent state.

    Returns:
        dict: Updates to the state (meal_plan_json, total_cost).
    """
    with st.status(
        "🧠 Planner: Designing Schedule & Analyzing Nutrition...", expanded=True
    ) as status:
        # Gemini 2.5 Pro with higher temperature for a bit of creativity
        llm = ChatGoogleGenerativeAI(
            model=PLANNER_MODEL,
            temperature=2.0,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
        # Meal Planner Prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    PLANNER_SYSTEM_PROMPT,
                ),
                ("human", "{input}"),
            ]
        )

        chain = prompt | llm
        response = await chain.ainvoke({"input": state["messages"][-1].content})

        try:
            content = re.sub(
                r"^```json|```$", "", response.content.strip(), flags=re.MULTILINE
            ).strip()
            json.loads(content)
            plan_json_str = content
        except (json.JSONDecodeError, TypeError):
            plan_json_str = json.dumps({"schedule": []})

        status.write("Plan created.")
    return {"meal_plan_json": plan_json_str, "total_cost": 0.0}


async def extractor_node(state: AgentState):
    """
    Extract a consolidated shopping list from the meal plan.

    Args:
        state (AgentState): The current agent state.

    Returns:
        dict: Updates to the state (shopping_list).
    """
    with st.status("📑 Extractor: Building Shopping List...", expanded=True) as status:
        llm = ChatGoogleGenerativeAI(
            model=EXTRACTOR_MODEL,
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

        past_buys = db.get_all_past_items()
        # Shopping List Extractor Prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    EXTRACTOR_SYSTEM_PROMPT,
                ),
                ("human", "{input}"),
            ]
        )

        response = await (prompt | llm).ainvoke(
            {
                "input": state["meal_plan_json"],
                "pantry": state.get("pantry_items", ""),
                "history": past_buys,
            }
        )

        raw_list = response.content.split(",")
        items = []
        for i in raw_list:
            clean = re.sub(r"\s+", " ", i).strip()
            if clean:
                items.append(clean)

        status.write(f"Identified {len(items)} items.")
    return {"shopping_list": items}


async def shopper_node(state: AgentState):
    """
    Execute the shopping process using the browser tool.

    Args:
        state (AgentState): The current agent state.

    Returns:
        dict: Updates to the state (cart_items, missing_items, total_cost).
    """
    shopping_list = state["shopping_list"]
    current_total = state.get("total_cost", 0.0)
    limit = state.get("budget_limit", 200.0)
    cart, missing = [], []
    
    # Gemini Flash for shopping
    llm = ChatGoogleGenerativeAI(
        model=SHOPPER_MODEL,
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )
    browser_tool = st.session_state.browser_tool

    status_container = st.status("🛒 Shopper: Smart Search Active...", expanded=True)
    if not browser_tool.page:
        await browser_tool.start()
    
    # --- STEP 1: OPTIMIZE QUERIES ---
    status_container.write("🧠 Optimizing search queries...")
    query_prompt = (
        "You are a search query optimizer for Amazon Fresh. \n"
        "Convert the following shopping list items into the BEST possible search queries.\n"
        "Remove specific quantities (like '2 cups', '1 lb') unless it's a standard pack size (like '12 pack').\n"
        "Keep brand names if specified. Keep dietary types (e.g. 'Gluten Free').\n"
        "Return a JSON object with a key 'queries' which is a list of strings corresponding to the input list.\n\n"
        f"Input List: {json.dumps(shopping_list)}"
    )
    try:
        q_response = await llm.ainvoke([HumanMessage(content=query_prompt)])
        content = re.sub(r"^```json|```$", "", q_response.content.strip(), flags=re.MULTILINE).strip()
        optimized_queries = json.loads(content)["queries"]
    except Exception:
        optimized_queries = shopping_list # Fallback

    progress_bar = status_container.progress(0)

    for i, (original_item, search_term) in enumerate(zip(shopping_list, optimized_queries)):
        status_container.write(f"Looking for: **{original_item}** (Query: *{search_term}*)")
        if current_total >= limit:
            missing.append(f"{original_item} (Budget Cut)")
            continue

        options = await browser_tool.search_and_get_options(search_term)

        if not options:
            # Fallback to original term if optimized failed
            if search_term != original_item:
                 options = await browser_tool.search_and_get_options(original_item)
            
            if not options:
                missing.append(original_item)
                continue

        # --- STEP 2: ENHANCED SELECTION ---
        choice_prompt = (
            f"User wants: '{original_item}'\n"
            f"Search Query used: '{search_term}'\n\n"
            "Available Options:\n"
        )
        for opt in options:
            choice_prompt += (
                f"Index {opt['index']}: {opt['title']}\n"
                f"   - Price: ${opt['price_str']}\n"
                f"   - Rating: {opt.get('rating', 'N/A')} ({opt.get('reviews', '0')} reviews)\n"
            )
        choice_prompt += (
            "\nINSTRUCTIONS:\n"
            "1. Identify the option that BEST matches the User's request.\n"
            "2. Consider quantity: If user wants '2 lbs' and option is '1 lb', that's okay (we can buy multiple later, but for now just pick the item).\n"
            "3. Consider value and ratings.\n"
            "4. If NO option is a good match, return -1.\n"
            "5. Return ONLY the Index integer (0, 1, 2...) or -1."
        )

        decision_msg = await llm.ainvoke([HumanMessage(content=choice_prompt)])
        try:
            choice_idx = int(re.search(r"-?\d+", decision_msg.content).group())
        except (AttributeError, ValueError):
            choice_idx = 0 # Default to first if unsure

        if choice_idx >= 0 and choice_idx < len(options):
            chosen = options[choice_idx]
            success = await browser_tool.add_specific_item(choice_idx)
            if success:
                cart.append(f"{chosen['title']} (${chosen['price_str']})")
                current_total += chosen['price']
            else:
                st.toast(f"Smart add failed for {original_item}. Retrying...")
                bf_result = await browser_tool.search_and_add(search_term)
                if bf_result["status"] == "ADDED":
                    cart.append(f"{original_item} (${bf_result['price']:.2f})")
                    current_total += bf_result["price"]
                else:
                    missing.append(original_item)
        else:
            missing.append(f"{original_item} (No good match)")

        progress_bar.progress((i + 1) / len(shopping_list))

    status_container.write("🚚 Initializing Checkout...")
    await browser_tool.trigger_checkout()
    status_container.update(
        label="Shopping Done. Handoff Initiated.", state="complete", expanded=False
    )
    return {"cart_items": cart, "missing_items": missing, "total_cost": current_total}


async def human_review_node(state: AgentState):
    """Placeholder node for human review (handled in UI)."""
    del state  # Unused argument
    return {}


async def checkout_node(state: AgentState):
    """Final node to signal completion."""
    del state  # Unused argument
    return {"messages": [SystemMessage(content="Handoff.")]}
