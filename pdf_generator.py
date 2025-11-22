"""
PDF generation module for Amazon Fresh Agent.

This module handles the creation of PDF meal plans and shopping lists using FPDF.
"""

import json
from typing import List

from fpdf import FPDF


class MealPlanPDF(FPDF):
    """
    Custom PDF class for meal plans.

    Inherits from FPDF.
    """

    def header(self):
        """Set up the PDF header."""
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "Amazon Fresh Fetch - Weekly Plan", 0, 1, "C")
        self.ln(5)

    def clean_text(self, text):
        """
        Sanitize text for PDF output.

        Args:
            text (str): The text to clean.

        Returns:
            str: The cleaned text encoded in latin-1.
        """
        if not text:
            return ""
        return text.encode("latin-1", "replace").decode("latin-1")


def generate_pdf(meal_json_str: str, shopping_list: List[str]) -> bytes:
    """
    Generate a PDF file containing the shopping list and meal plan.

    Args:
        meal_json_str (str): The JSON string of the meal plan.
        shopping_list (List[str]): The list of shopping items.

    Returns:
        bytes: The generated PDF file as bytes.
    """
    pdf = MealPlanPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Master Shopping List", 0, 1, "L")
    pdf.set_font("Arial", "", 10)
    col_width = 90
    for i in range(0, len(shopping_list), 2):
        item1 = shopping_list[i]
        item2 = shopping_list[i + 1] if i + 1 < len(shopping_list) else ""
        pdf.cell(col_width, 7, f"[ ] {pdf.clean_text(item1)}", 0, 0)
        if item2:
            pdf.cell(col_width, 7, f"[ ] {pdf.clean_text(item2)}", 0, 1)
        else:
            pdf.ln(7)
    pdf.ln(10)

    try:
        data = json.loads(meal_json_str)
        schedule = data.get("schedule", [])
        for day in schedule:
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.set_text_color(255, 75, 75)
            pdf.cell(0, 10, pdf.clean_text(day["day"]), 0, 1, "L")
            pdf.set_text_color(0, 0, 0)
            for meal_type in ["breakfast", "lunch", "dinner"]:
                meal_data = day.get(meal_type)
                if isinstance(meal_data, dict):
                    pdf.set_font("Arial", "B", 12)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(
                        0,
                        8,
                        f"{meal_type.title()}: {pdf.clean_text(meal_data.get('title', ''))}",
                        0,
                        1,
                        "L",
                        fill=True,
                    )
                    pdf.set_font("Arial", "", 10)
                    pdf.multi_cell(
                        0, 5, f"Ing: {pdf.clean_text(meal_data.get('ingredients', ''))}"
                    )
                    pdf.multi_cell(
                        0,
                        5,
                        f"Steps: {pdf.clean_text(meal_data.get('instructions', ''))}",
                    )
                    pdf.ln(5)
    except (json.JSONDecodeError, TypeError):
        pass
    return pdf.output(dest="S").encode("latin-1")
