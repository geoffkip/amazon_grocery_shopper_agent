# 🥕 Amazon Fresh Fetch AI Agent

<div align="center">

**An intelligent AI-powered shopping assistant that creates meal plans and automatically adds groceries to your Amazon Fresh cart**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Latest-green.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## ✨ Features

- 🧠 **AI Meal Planning**: Generate personalized weekly meal plans using Google Gemini 2.5 Pro AI with detailed nutrition analysis
- 📝 **Smart Shopping Lists**: Automatically extract ingredients from meal plans with quantity consolidation, accounting for pantry items
- 🎓 **Preference Learning**: Learns from your shopping history to suggest preferred brands and products you've bought before
- 🤖 **Intelligent Product Selection**: LLM-powered product matching that analyzes top 3 search results to pick the best value/match with automatic fallback
- 🛒 **Automated Cart Management**: Seamlessly search and add items to your Amazon Fresh cart with real-time price tracking
- 💰 **Budget Tracking**: Monitor spending in real-time with configurable budget limits and automatic budget cutoffs
- 📊 **Nutritional Analysis**: Visual charts showing daily calories, protein, carbs, and fat breakdowns
- 📄 **PDF Export**: Generate downloadable meal plan PDFs with shopping lists and recipe instructions
- 💾 **History & Persistence**: SQLite database stores meal plans, shopping lists, and settings for easy review
- 🔄 **One-Click Reordering**: Easily reload past meal plans to shop for them again
- 🗑️ **Granular History Control**: Delete individual meal plans or clear entire history
- 🎯 **Customizable Preferences**: Set dietary restrictions, pantry items, and budget constraints
- 🍪 **Session Persistence**: Save browser sessions to avoid repeated logins
- 🎨 **Interactive UI**: Beautiful Streamlit interface with real-time progress tracking, meal cards, and tabbed weekly views

## 🏗️ Architecture

This project uses **LangGraph** to orchestrate a multi-step workflow:

```
User Input → Planner → Extractor → Shopper → Human Review → Checkout
```

### Workflow Nodes

1. **Planner Node**: 
   - Analyzes user meal preferences using Google Gemini 2.5 Pro AI
   - Generates a structured weekly meal plan with breakfast, lunch, and dinner
   - Includes detailed ingredients with quantities (lbs, oz, cups, count)
   - Calculates daily nutritional information (calories, protein, carbs, fat)
   - Uses higher temperature (0.7) for creative meal planning

2. **Extractor Node**: 
   - Parses meal plan JSON to extract all ingredients using Google Gemini 2.5 Pro
   - Consolidates duplicate items by summing quantities
   - Filters out pantry items that the user already has
   - **Preference Learning**: Analyzes past shopping history to learn brand preferences
   - Automatically upgrades generic items (e.g., "Peanut Butter") to specific brands you've bought before (e.g., "Smuckers Peanut Butter")
   - Returns a clean, deduplicated shopping list with improved text cleaning

3. **Shopper Node**: 
   - Searches Amazon Fresh for each item
   - Scrapes top 3 search results with titles and prices
   - Uses Google Gemini 2.5 Flash to intelligently select the best match/value from options
   - **Smart Fallback**: If AI selection fails, automatically retries with brute-force first-result method
   - Adds selected items to cart with real-time budget tracking
   - Handles missing items and budget cutoffs gracefully
   - Automatically navigates to checkout when complete

4. **Human Review Node**: 
   - Pauses workflow for user to review and edit shopping list
   - Allows manual item removal/addition before shopping begins
   - Provides PDF download option for meal plan

5. **Checkout Node**: 
   - Navigates to Amazon cart
   - Attempts multiple checkout button strategies (Fresh Cart, Proceed to checkout, etc.)
   - Displays comprehensive review with success rate metrics
   - Shows separate columns for successfully added items vs. missed items
   - Handles checkout initiation, then terminates for manual user completion

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Google API Key for Gemini AI
- Amazon account with Amazon Fresh access
- Chrome/Chromium browser (for Playwright)

### Installation

#### Option 1: Manual Installation (Recommended)

1.  **Clone the repository**
    ```bash
    git clone https://github.com/YOUR_USERNAME/amazon_agent.git
    cd amazon_agent
    ```

2.  **Create and activate a virtual environment**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright browsers**
    ```bash
    playwright install chromium
    ```

5.  **Set up API Key (Optional)**
    
    You can create a `.env` file in the project root:
    ```env
    GOOGLE_API_KEY=your_google_api_key_here
    ```
    
    **OR** simply run the app, and it will ask for your key in the sidebar if one is not found.
    
    Get your Google API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

    Note: The first time you run the app, you'll need to manually log in to Amazon in the browser window that opens. Your session will be saved for future runs.

#### Option 2: Standalone Executable (Alternative)

If you prefer a single file executable or want to distribute the app:

> **Note**: You must run the build script on the same operating system you are building for (e.g., run on Windows to build a `.exe`, run on Mac to build a Mac app).

1.  **Build the executable** (requires Python installed once for the build):
    ```bash
    pip install -r requirements.txt
    python build_executable.py
    ```
2.  **Run the app**:
    - Go to the `dist/` folder.
    - Double-click `AmazonFreshAgent` (Mac) or `AmazonFreshAgent.exe` (Windows).
    - You can move this single file anywhere on your computer.

### Running the Application

```bash
streamlit run amazon_fresh_fetch.py
```

The application will open in your default browser (typically at `http://localhost:8501` or `http://localhost:8503`)

**First Run**: A Chrome browser window will open for Amazon Fresh. You'll need to manually log in once. Your session will be saved automatically.

## 📖 Usage

### 1. Configure Settings

In the sidebar, set:
- **Weekly Budget**: Your spending limit (default: $200)
- **Pantry Items**: Items you already have (e.g., "Salt, Pepper, Olive Oil")

### 2. Create a Meal Plan

Enter your meal preferences in the text area. Example:
```
Create a weekly meal plan for 2 adults with:
- Healthy meals ready in 30 minutes
- Monday-Friday dinner and lunch
- No pork, vegetarian options preferred
- Focus on whole grains and 30g protein per meal
```

### 3. Review and Edit

- Review the generated meal plan with nutritional charts
- View meal details in organized day-by-day tabs
- Edit the shopping list (add/remove items using the data editor)
- Download a PDF version of your meal plan
- Confirm to start shopping

### 4. Automated Shopping

The agent will:
- Search for each item on Amazon Fresh
- Scrape top 3 search results with prices
- Use AI to intelligently select the best product match/value
- Add selected items to your cart automatically
- Track prices and budget in real-time
- Handle missing items and budget cutoffs gracefully

### 5. Final Review & Checkout

- View comprehensive summary with success rate percentage
- See separate sections for successfully added items vs. missed items
- Review total cost, budget status, and cart statistics
- The browser will automatically navigate to checkout with multiple fallback strategies
- Complete payment, delivery time, and final order confirmation manually in the browser window

### 6. History Management

- **View Past Plans**: Click on any date in the "History" sidebar to view that meal plan.
- **Download PDF**: When viewing a past plan, click "📄 Download PDF Plan" to get a copy.
- **Reorder**: Click "🔄 Reorder" to load a past plan back into the main view and shop for it again.
- **Delete**: Click the trash icon (🗑️) next to a specific plan to remove it, or use "Clear History" to remove everything.

## 🛠️ Technology Stack

- **Streamlit**: Web UI framework with interactive components
- **LangGraph**: Workflow orchestration and state management with checkpoints
- **LangChain**: LLM integration and prompt management
- **Google Gemini 2.5 Pro**: AI model for meal planning and ingredient extraction (with preference learning)
- **Google Gemini 2.5 Flash**: AI model for fast product selection during shopping
- **Playwright**: Browser automation for Amazon Fresh interaction
- **SQLite**: Local database for meal plan history and settings
- **FPDF**: PDF generation for meal plan exports
- **Pandas**: Data manipulation for nutritional analysis and shopping lists
- **Python**: Core language (3.8+)

## 📁 Project Structure

```
amazon_agent/
├── amazon_fresh_fetch.py    # Main application entry point (UI & Orchestration)
├── workflow.py              # LangGraph workflow definition
├── agent.py                 # Agent nodes and logic
├── browser.py               # Browser automation logic
├── database.py              # Database interactions
├── prompts.py               # Centralized AI prompts
├── ui.py                    # UI components and styles
├── utils.py                 # Utility functions
├── config.py                # Configuration settings
├── pdf_generator.py         # PDF generation logic
├── amazon_session.json      # Browser session storage (gitignored)
├── agent_data.db            # SQLite database for meal plans & settings (gitignored)
├── .env                     # Environment variables (gitignored)
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── user_session/            # Chrome browser session data (gitignored)
├── packaging/               # PyInstaller packaging scripts
├── build_executable.py      # Script to build standalone executable
└── README.md                # This file
```

## 🔒 Security & Privacy

- **Session Data**: Browser sessions are stored locally in `amazon_session.json` (gitignored)
- **Database**: SQLite database `agent_data.db` stores meal plans locally (gitignored)
- **API Keys**: Store your Google API key in `.env` file (gitignored)
- **Browser Data**: Chrome session data in `user_session/` directory (gitignored)
- **Credentials**: Never commit sensitive information to the repository

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Your Google Gemini API key | Yes |

### Budget Limits

Set your weekly budget in the Streamlit sidebar. The agent will stop adding items once the budget is reached.

### Pantry Management

List items you already have in your pantry. The agent will exclude these from the shopping list.

### Preference Learning

The agent automatically learns from your shopping history stored in the database. When you request a generic item (e.g., "Peanut Butter"), it will suggest the specific brand you've purchased before (e.g., "Smuckers Natural Peanut Butter"). This preference learning improves over time as you create more meal plans.

## 🛠️ Utility Scripts

The `scripts/` directory contains helpful tools for managing your data:

### 1. Import Purchase History (`scripts/import_receipt.py`)
Train the AI on your past purchases to improve brand recommendations.
1. Copy the text from your Amazon Fresh order history (or email receipt).
2. Paste it into the `RAW_DATA` variable in `scripts/import_receipt.py`.
3. Run the script:
   ```bash
   python scripts/import_receipt.py
   ```

### 2. Inspect Database (`scripts/check_db.py`)
View the contents of your local database without needing a SQL client.
- Shows all tables
- Lists top 20 most frequent items in purchase history
- Displays saved settings
- Summarizes recent meal plans
   ```bash
   python scripts/check_db.py
   ```

## 🐛 Troubleshooting

### Browser Not Launching
- Ensure Playwright browsers are installed: `playwright install chromium`
- Check that Chrome/Chromium is available on your system

### Login Issues
- The browser will pause for manual login on first run
- Session is saved to `amazon_session.json` for future runs
- Delete the session file to force re-login

### Items Not Found
- The agent uses AI to select the best match from search results
- If AI selection fails, it automatically falls back to adding the first search result
- Items that can't be matched or exceed budget appear in the "Missing/Skipped" section
- You can manually add items in the browser window if needed

### Database Issues
- The SQLite database (`agent_data.db`) is created automatically on first run
- If you encounter database errors, you can delete `agent_data.db` to start fresh
- Your meal plan history will be lost if you delete the database

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [LangGraph](https://langchain-ai.github.io/langgraph/) for workflow orchestration
- Powered by [Google Gemini AI](https://deepmind.google/technologies/gemini/)
- UI created with [Streamlit](https://streamlit.io/)
- Browser automation via [Playwright](https://playwright.dev/)

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

<div align="center">

**Made with ❤️ for easier grocery shopping**

⭐ Star this repo if you find it helpful!

</div>


