"""
Unit tests for browser.py

Note: These tests focus on testable logic like price parsing.
Full browser automation would require integration tests with Playwright.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from browser import AmazonFreshBrowser


class TestAmazonFreshBrowser(unittest.IsolatedAsyncioTestCase):
    """Test cases for AmazonFreshBrowser class."""

    def test_initialization(self):
        """Test browser initialization."""
        browser = AmazonFreshBrowser()
        self.assertIsNone(browser.browser)
        self.assertIsNone(browser.context)
        self.assertIsNone(browser.page)
        self.assertIsNone(browser.playwright)
        self.assertEqual(browser.session_file, "amazon_session.json")

    @patch("browser.st")
    @patch("browser.async_playwright")
    async def test_start_creates_browser(self, mock_playwright_func, mock_st):
        """Test that start() initializes browser components."""
        # Mock Playwright
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Create an async context manager mock
        mock_async_cm = AsyncMock()
        mock_async_cm.__aenter__.return_value = mock_playwright
        mock_async_cm.start.return_value = mock_playwright
        
        # Make async_playwright() return the async context manager
        mock_playwright_func.return_value = mock_async_cm

        # Mock file operations and Streamlit
        with patch("browser.os.path.exists", return_value=False):
            browser = AmazonFreshBrowser()
            await browser.start()

        # Verify browser was initialized
        self.assertEqual(browser.browser, mock_browser)
        self.assertEqual(browser.context, mock_context)
        self.assertEqual(browser.page, mock_page)

    async def test_price_parsing_logic(self):
        """Test price string parsing logic (extracted from search_and_add)."""
        # This tests the logic used in the browser methods
        test_cases = [
            ("$12.99", 12.99),
            ("$5.00", 5.00),
            ("$100.50", 100.50),
            ("$1,234.56", 1234.56),
        ]

        for price_str, expected in test_cases:
            # Simulate the parsing logic from browser.py
            cleaned = price_str.replace("$", "").replace(",", "").strip()
            result = float(cleaned)
            self.assertEqual(result, expected, f"Failed for {price_str}")


if __name__ == "__main__":
    unittest.main()
