"""
Utility functions for the Amazon Fresh Fetch Agent.
"""

import os
import streamlit as st

def get_api_key():
    """Get API key from Environment OR Sidebar"""
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        # If no .env file, show an input box in the sidebar
        with st.sidebar:
            st.divider()
            st.warning("🔑 API Key Required")
            api_key = st.text_input(
                "Enter Gemini API Key:", 
                type="password", 
                help="Get one at aistudio.google.com"
            )
            if api_key:
                os.environ["GOOGLE_API_KEY"] = api_key # Set for this session
                st.success("Key Accepted!")
                st.rerun() # Rerun to ensure key is picked up
            else:
                st.stop() # Stop execution until key is provided
    return api_key
