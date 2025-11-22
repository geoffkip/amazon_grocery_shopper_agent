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

from database import db


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
            model="gemini-2.5-pro",
            temperature=0.7,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
        # Meal Planner Prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a professional chef. Create a JSON object with ONE key: "schedule".
            The "schedule" is an array of objects. Each object represents a DAY and must have:
            - "day": "Monday", "Tuesday", etc.
            - "breakfast": {{ "title": "Name", "ingredients": "Specific list with quantities (e.g. '2 Eggs', '1 cup Oats')", "instructions": "Steps" }}
            - "lunch": {{ "title": "Name", "ingredients": "Specific list with quantities (e.g. '4oz Chicken', '1 Avocado')", "instructions": "Steps" }}
            - "dinner": {{ "title": "Name", "ingredients": "Specific list with quantities (e.g. '1lb Beef', '1 cup Rice')", "instructions": "Steps" }}
            - "nutrition": {{ "calories": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 70 }}
            
            CRITICAL: You must list specific quantities (lbs, oz, cups, count) for every ingredient so the shopping list is accurate.
            """,
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
            model="gemini-2.5-pro",
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

        past_buys = db.get_all_past_items()
        # Shopping List Extractor Prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a rigorous shopping list compiler.
            1. Read the provided JSON meal plan.
            2. Extract the 'ingredients' string from EVERY meal.
            3. Consolidate items by summing up quantities where possible (e.g., "2 eggs" + "2 eggs" = "4 Eggs").
            4. Compare against PANTRY: {pantry}. Remove any matches.
            5. Check HISTORY below. If a generic item (e.g. "Peanut Butter") matches a brand in history (e.g. "Smuckers"), use the specific one.
            6. STRICT OUTPUT RULE: Return ONLY a comma-separated list of items. Do not speak. Do not add introduction text.
            
            HISTORY: {history}
            """,
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
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )
    browser_tool = st.session_state.browser_tool

    status_container = st.status("🛒 Shopper: Smart Search Active...", expanded=True)
    if not browser_tool.page:
        await browser_tool.start()
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
        for opt in options:
            choice_prompt += (
                f"Index {opt['index']}: {opt['title']} - ${opt['price_str']}\n"
            )
        choice_prompt += (
            "Return ONLY the Index integer (0, 1, or 2) of the best match/value."
        )

        decision_msg = await llm.ainvoke([HumanMessage(content=choice_prompt)])
        try:
            choice_idx = int(re.search(r"-?\d+", decision_msg.content).group())
        except (AttributeError, ValueError):
            choice_idx = 0

        if 0 <= choice_idx < len(options):
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
