"""
Unit tests for pdf_generator.py
"""

import json
import unittest

from pdf_generator import MealPlanPDF, generate_pdf


class TestMealPlanPDF(unittest.TestCase):
    """Test cases for MealPlanPDF class."""

    def test_clean_text(self):
        """Test text cleaning functionality."""
        pdf = MealPlanPDF()
        
        # Test normal text
        self.assertEqual(pdf.clean_text("Hello World"), "Hello World")
        
        # Test empty string
        self.assertEqual(pdf.clean_text(""), "")
        
        # Test None
        self.assertEqual(pdf.clean_text(None), "")
        
        # Test special characters
        result = pdf.clean_text("Café ñoño")
        self.assertIsInstance(result, str)


class TestGeneratePDF(unittest.TestCase):
    """Test cases for generate_pdf function."""

    def test_generate_pdf_basic(self):
        """Test basic PDF generation."""
        meal_plan = json.dumps({
            "schedule": [
                {
                    "day": "Monday",
                    "breakfast": {
                        "title": "Scrambled Eggs",
                        "ingredients": "2 Eggs, 1 tbsp Butter",
                        "instructions": "Beat eggs and cook in butter."
                    },
                    "lunch": {
                        "title": "Chicken Salad",
                        "ingredients": "4oz Chicken, Lettuce",
                        "instructions": "Grill chicken and toss with lettuce."
                    },
                    "dinner": {
                        "title": "Steak",
                        "ingredients": "8oz Steak, Salt",
                        "instructions": "Season and grill steak."
                    }
                }
            ]
        })
        
        shopping_list = ["Eggs", "Butter", "Chicken", "Lettuce", "Steak", "Salt"]
        
        result = generate_pdf(meal_plan, shopping_list)
        
        # Check that it returns bytes
        self.assertIsInstance(result, bytes)
        
        # Check that it's a valid PDF (starts with PDF header)
        self.assertTrue(result.startswith(b"%PDF"))

    def test_generate_pdf_empty_shopping_list(self):
        """Test PDF generation with empty shopping list."""
        meal_plan = json.dumps({"schedule": []})
        shopping_list = []
        
        result = generate_pdf(meal_plan, shopping_list)
        
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"))

    def test_generate_pdf_invalid_json(self):
        """Test PDF generation with invalid JSON."""
        meal_plan = "invalid json"
        shopping_list = ["Item"]
        
        # Should not crash, just generate PDF with shopping list
        result = generate_pdf(meal_plan, shopping_list)
        
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
