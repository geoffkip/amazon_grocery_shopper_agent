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

- 🧠 **AI Meal Planning**: Generate personalized weekly meal plans using Google Gemini AI
- 📝 **Smart Shopping Lists**: Automatically extract ingredients from meal plans, accounting for pantry items
- 🛒 **Automated Cart Management**: Seamlessly search and add items to your Amazon Fresh cart
- 💰 **Budget Tracking**: Monitor spending in real-time with configurable budget limits
- 🔄 **Substitution Logic**: Intelligent item substitution when products are unavailable
- 🎯 **Customizable Preferences**: Set dietary restrictions, pantry items, and budget constraints
- 🍪 **Session Persistence**: Save browser sessions to avoid repeated logins
- 📊 **Interactive UI**: Beautiful Streamlit interface with real-time progress tracking

## 🏗️ Architecture

This project uses **LangGraph** to orchestrate a multi-step workflow:

```
User Input → Planner → Extractor → Shopper → Human Review → Checkout
```

### Workflow Nodes

1. **Planner Node**: Analyzes user meal preferences and generates a weekly meal plan
2. **Extractor Node**: Extracts shopping list items, excluding pantry items
3. **Shopper Node**: Searches Amazon Fresh and adds items to cart with budget tracking
4. **Human Review Node**: Pauses for user approval before checkout
5. **Checkout Node**: Navigates to the cart and clicks "Check out Fresh Cart," then terminates to allow manual user completion.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Google API Key for Gemini AI
- Amazon account with Amazon Fresh access
- Chrome/Chromium browser (for Playwright)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/amazon_agent.git
   cd amazon_agent
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the project root:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   ```

5. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

### Running the Application

```bash
streamlit run amazon_agent.py
```

The application will open in your default browser at `http://localhost:8501`

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

- Review the generated meal plan
- Edit the shopping list (add/remove items)
- Confirm to start shopping

### 4. Automated Shopping

The agent will:
- Search for each item on Amazon Fresh
- Add items to your cart
- Track prices and budget
- Suggest substitutions for unavailable items

### 5. Final Review

- Proceed to Cart Checkout
- Switches to manual user handout mode
- Review missing items, substitution items, select payment and delivery time
- Place final order and confirm

## 🛠️ Technology Stack

- **Streamlit**: Web UI framework
- **LangGraph**: Workflow orchestration and state management
- **LangChain**: LLM integration
- **Google Gemini AI**: Meal planning and list extraction
- **Playwright**: Browser automation
- **Python**: Core language

## 📁 Project Structure

```
amazon_agent/
├── amazon_agent.py          # Main application file
├── amazon_session.json       # Browser session storage (gitignored)
├── .env                      # Environment variables (gitignored)
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🔒 Security & Privacy

- **Session Data**: Browser sessions are stored locally in `amazon_session.json` (not committed to git)
- **API Keys**: Store your Google API key in `.env` file (not committed to git)
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

## 🐛 Troubleshooting

### Browser Not Launching
- Ensure Playwright browsers are installed: `playwright install chromium`
- Check that Chrome/Chromium is available on your system

### Login Issues
- The browser will pause for manual login on first run
- Session is saved to `amazon_session.json` for future runs
- Delete the session file to force re-login

### Items Not Found
- The agent will attempt substitutions automatically
- Check the "Missing/Skipped" section in the final review
- Manually add items if needed

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


