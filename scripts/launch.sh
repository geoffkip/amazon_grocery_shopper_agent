#!/bin/bash
# Amazon Fresh Fetch - macOS/Linux Launcher

# Activate virtual environment
source .venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please run install.sh first"
    exit 1
fi

# Launch the app
echo "🚀 Launching Amazon Fresh Fetch..."
echo "Opening in your browser..."
echo ""
echo "Press Ctrl+C to stop the app"
echo ""

# Open browser after a short delay
(sleep 2 && open http://localhost:8501) &

# Start Streamlit
streamlit run amazon_fresh_fetch.py
