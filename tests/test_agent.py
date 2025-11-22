"""
Unit tests for agent.py
"""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import planner_node, extractor_node


class TestPlannerNode(unittest.IsolatedAsyncioTestCase):
    """Test cases for planner_node."""

    @patch("agent.st")
    @patch("agent.ChatGoogleGenerativeAI")
    async def test_planner_node_valid_json(self, mock_llm_class, mock_st):
        """Test planner node with valid JSON response."""
        # Mock Streamlit status
        mock_status = MagicMock()
        mock_st.status.return_value.__enter__.return_value = mock_status

        # Mock LLM response
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        valid_plan = {"schedule": [{"day": "Monday"}]}
        mock_response.content = json.dumps(valid_plan)
        mock_llm.ainvoke.return_value = mock_response
        
        # Mock chain
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        # Create state
        state = {
            "messages": [MagicMock(content="Create a meal plan")]
        }

        # Patch the chain creation
        with patch("agent.ChatPromptTemplate") as mock_template:
            mock_template.from_messages.return_value.__or__ = MagicMock(return_value=mock_chain)
            
            result = await planner_node(state)

        # Verify result
        self.assertIn("meal_plan_json", result)
        self.assertEqual(result["total_cost"], 0.0)
        parsed = json.loads(result["meal_plan_json"])
        self.assertIn("schedule", parsed)

    @patch("agent.st")
    @patch("agent.ChatGoogleGenerativeAI")
    async def test_planner_node_invalid_json(self, mock_llm_class, mock_st):
        """Test planner node handles invalid JSON gracefully."""
        # Mock Streamlit
        mock_status = MagicMock()
        mock_st.status.return_value.__enter__.return_value = mock_status

        # Mock LLM with invalid response
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        mock_llm.ainvoke.return_value = mock_response
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        state = {
            "messages": [MagicMock(content="Create a meal plan")]
        }

        with patch("agent.ChatPromptTemplate") as mock_template:
            mock_template.from_messages.return_value.__or__ = MagicMock(return_value=mock_chain)
            
            result = await planner_node(state)

        # Should return fallback empty schedule
        parsed = json.loads(result["meal_plan_json"])
        self.assertEqual(parsed, {"schedule": []})


class TestExtractorNode(unittest.IsolatedAsyncioTestCase):
    """Test cases for extractor_node."""

    @patch("agent.st")
    @patch("agent.db")
    @patch("agent.ChatGoogleGenerativeAI")
    async def test_extractor_node_basic(self, mock_llm_class, mock_db, mock_st):
        """Test extractor node with basic shopping list."""
        # Mock Streamlit
        mock_status = MagicMock()
        mock_st.status.return_value.__enter__.return_value = mock_status

        # Mock database
        mock_db.get_all_past_items.return_value = "Eggs, Milk"

        # Mock LLM response
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Eggs, Bread, Butter"
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        state = {
            "meal_plan_json": json.dumps({"schedule": []}),
            "pantry_items": "Salt, Pepper"
        }

        with patch("agent.ChatPromptTemplate") as mock_template:
            mock_template.from_messages.return_value.__or__ = MagicMock(return_value=mock_chain)
            
            result = await extractor_node(state)

        # Verify shopping list
        self.assertIn("shopping_list", result)
        self.assertEqual(len(result["shopping_list"]), 3)
        self.assertIn("Eggs", result["shopping_list"])
        self.assertIn("Bread", result["shopping_list"])
        self.assertIn("Butter", result["shopping_list"])


if __name__ == "__main__":
    unittest.main()
