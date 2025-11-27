"""
Browser automation module for Amazon Fresh Agent.

This module handles the interaction with the Amazon Fresh website using Playwright,
including searching for items, adding them to the cart, and initiating checkout.
"""

import asyncio
import os
from typing import Dict, List

import streamlit as st
from playwright.async_api import async_playwright

from config import SESSION_FILE


class AmazonFreshBrowser:
    """
    Controls the browser for Amazon Fresh shopping.

    Attributes:
        browser (Browser): The Playwright browser instance.
        context (BrowserContext): The browser context.
        page (Page): The current browser page.
        playwright (Playwright): The Playwright instance.
        session_file (str): Path to the session storage file.
    """

    def __init__(self):
        """Initialize the AmazonFreshBrowser."""
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.session_file = SESSION_FILE

    async def start(self):
        """
        Launch the browser and navigate to Amazon Fresh.

        Loads the session if available, otherwise starts a new session.
        """
        if self.page:
            return
        st.toast("🚀 Launching Browser...")
        self.playwright = await async_playwright().start()
        st.toast("🚀 Launching Browser...")
        self.playwright = await async_playwright().start()
        
        try:
            self.browser = await self.playwright.chromium.launch(
                headless=False, slow_mo=1000
            )
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                st.warning("⚠️ Browser not found. Installing Chromium... This may take a minute.")
                import subprocess
                import sys
                
                # Install chromium
                try:
                    # Try installing via the python module
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                    st.success("✅ Browser installed! Retrying launch...")
                    
                    # Retry launch
                    self.browser = await self.playwright.chromium.launch(
                        headless=False, slow_mo=1000
                    )
                except Exception as install_error:
                    st.error(f"❌ Failed to install browser: {install_error}")
                    raise e
            else:
                raise e

        if os.path.exists(self.session_file):
            self.context = await self.browser.new_context(
                storage_state=self.session_file, viewport={"width": 1280, "height": 720}
            )
            st.toast("🍪 Session loaded")
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720}
            )

        self.page = await self.context.new_page()
        await self.page.goto(
            "https://www.amazon.com/alm/storefront?almBrandId=QW1hem9uIEZyZXNo"
        )

        try:
            if (
                await self.page.locator("#nav-link-accountList-nav-line-1")
                .filter(has_text="Sign in")
                .count()
                > 0
            ):
                st.warning("⚠️ Please Log In manually in the browser window!")
                await asyncio.sleep(60)
                await self.context.storage_state(path=self.session_file)
        except Exception:
            pass
        st.success("✅ Browser Ready")

    # --- BRUTE FORCE ADD ---
    async def search_and_add(self, item_name: str) -> dict:
        """
        Search for an item and add the first result to the cart.

        Args:
            item_name (str): The name of the item to search for.

        Returns:
            dict: A dictionary containing the status ("ADDED", "NOT_FOUND", "ERROR") and price.
        """
        try:
            search_box = self.page.locator('input[id="twotabsearchtextbox"]')
            await search_box.clear()
            await search_box.fill(item_name)
            await search_box.press("Enter")
            
            try:
                # Smart wait for results
                await self.page.wait_for_selector(
                    'div[data-component-type="s-search-result"]', 
                    state="attached", 
                    timeout=5000
                )
            except Exception:
                return {"status": "NOT_FOUND", "price": 0.0}

            results = await self.page.locator(
                'div[data-component-type="s-search-result"]'
            ).all()
            
            if not results:
                return {"status": "NOT_FOUND", "price": 0.0}
            
            # Try the first few results in case the first one is unavailable
            for target_card in results[:3]:
                price = 0.0
                try:
                    price_el = target_card.locator(".a-price .a-offscreen").first
                    if await price_el.count() > 0:
                        txt = await price_el.text_content()
                        price = float(txt.replace("$", "").replace(",", "").strip())
                except Exception:
                    pass

                # Try multiple button selectors
                btn = target_card.get_by_role("button", name="Add to cart")
                if await btn.count() == 0:
                    btn = target_card.locator("button[name='submit.addToCart']")
                if await btn.count() == 0:
                    btn = target_card.locator("input[name='submit.addToCart']")

                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    # Wait for cart count to update or a success message? 
                    # For now, just a small buffer is safer than nothing, but we rely on the UI not erroring.
                    await asyncio.sleep(1) 
                    return {"status": "ADDED", "price": price}

            return {"status": "NOT_FOUND", "price": 0.0}
        except Exception:
            return {"status": "ERROR", "price": 0.0}

    # --- SMART SHOPPER LOGIC ---
    async def search_and_get_options(self, item_name: str) -> List[Dict]:
        """
        Search for an item and return the top 5 results with details.

        Args:
            item_name (str): The name of the item to search for.

        Returns:
            List[Dict]: A list of dictionaries containing item details.
        """
        try:
            search_box = self.page.locator('input[id="twotabsearchtextbox"]')
            await search_box.clear()
            await search_box.fill(item_name)
            await search_box.press("Enter")
            
            try:
                await self.page.wait_for_selector(
                    'div[data-component-type="s-search-result"]', 
                    state="attached",
                    timeout=5000
                )
            except Exception:
                return []

            results = await self.page.locator(
                'div[data-component-type="s-search-result"]'
            ).all()
            
            options = []
            # Check top 5 results
            for i, res in enumerate(results[:5]):
                try:
                    title = await res.locator("h2").first.text_content()
                    
                    # Price
                    price_text = "0.00"
                    if await res.locator(".a-price .a-offscreen").count() > 0:
                        price_text = await res.locator(".a-price .a-offscreen").first.text_content()
                    
                    # Rating (e.g. "4.5 out of 5 stars")
                    rating = "N/A"
                    rating_el = res.locator("i.a-icon-star-small span.a-icon-alt")
                    if await rating_el.count() > 0:
                        rating = await rating_el.first.text_content()
                    
                    # Review Count
                    reviews = "0"
                    review_el = res.locator("span.a-size-base.s-underline-text")
                    if await review_el.count() > 0:
                        reviews = await review_el.first.text_content()

                    options.append(
                        {
                            "index": i,
                            "title": title.strip(),
                            "price_str": price_text.strip(),
                            "price": (
                                float(price_text.replace("$", "").replace(",", "").strip())
                                if "$" in price_text
                                else 0.0
                            ),
                            "rating": rating.strip(),
                            "reviews": reviews.strip()
                        }
                    )
                except Exception:
                    continue
            return options
        except Exception:
            return []

    async def add_specific_item(self, index: int) -> bool:
        """
        Add a specific item from the search results to the cart.

        Args:
            index (int): The index of the item in the search results.

        Returns:
            bool: True if added successfully, False otherwise.
        """
        try:
            results = await self.page.locator(
                'div[data-component-type="s-search-result"]'
            ).all()
            if index >= len(results):
                return False
            target = results[index]

            btn = target.get_by_role("button", name="Add to cart")
            if await btn.count() == 0:
                btn = target.locator("button[name='submit.addToCart']")
            if await btn.count() == 0:
                btn = target.locator("input[name='submit.addToCart']")

            if await btn.count() > 0:
                await btn.first.scroll_into_view_if_needed()
                if await btn.first.is_visible():
                    await btn.first.click()
                    await asyncio.sleep(1)
                    return True
            return False
        except Exception:
            return False

    async def trigger_checkout(self):
        """
        Navigate to the cart and initiate the checkout process.

        Returns:
            bool: True if checkout initiated successfully, False otherwise.
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
            proceed_btn = self.page.locator(
                "input[name='proceedToALMCheckout-QW1hem9uIEZyZXNo']"
            )
            if await proceed_btn.count() > 0:
                await proceed_btn.click()
                return True
            fallback = self.page.get_by_role("button", name="Proceed to checkout")
            if await fallback.count() > 0:
                await fallback.click()
                return True
        except Exception:
            return False
        return False

    async def close(self):
        """Close the browser and save the session."""
        if self.context:
            await self.context.storage_state(path=self.session_file)
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
