"""
LangGraph workflow definition for Amazon Fresh Fetch Agent.
"""

import streamlit as st
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


def create_workflow():
    """
    Create and compile the LangGraph workflow.

    Returns:
        CompiledGraph: The compiled state graph.
    """
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
    
    return workflow.compile(
        checkpointer=MemorySaver(), interrupt_before=["shopper", "checkout"]
    )


def init_session_state():
    """Initialize the session state with the workflow and browser tool."""
    if "graph_app" not in st.session_state:
        st.session_state.graph_app = create_workflow()
        st.session_state.browser_tool = AmazonFreshBrowser()
