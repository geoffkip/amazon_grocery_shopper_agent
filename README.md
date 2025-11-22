# Amazon Fresh Fetch

AI-powered meal planning and Amazon Fresh shopping automation.

## 🚀 Quick Start for End Users

**Download the latest release**: [Releases](https://github.com/geoffkip/Amazon-Fresh-Fetch/releases)

See [README_INSTALLATION.md](README_INSTALLATION.md) for detailed installation instructions.

---

## 🛠️ Developer Setup

For developers who want to run from source:

### Prerequisites
- Python 3.8+
- Virtual environment recommended

### Installation

```bash
# Clone the repository
git clone https://github.com/geoffkip/Amazon-Fresh-Fetch.git
cd amazon-fresh-fetch

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Mac/Linux
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Create .env file
echo "GOOGLE_API_KEY=your_key_here" > .env

# Run the app
streamlit run amazon_fresh_fetch.py
```

---

## 📁 Project Structure

```
amazon_agent/
├── amazon_fresh_fetch.py   # Main Streamlit app
├── agent.py                # LangGraph agent nodes
├── browser.py              # Playwright browser automation
├── database.py             # SQLite database manager
├── pdf_generator.py        # PDF meal plan generator
├── config.py               # Configuration constants
├── tests/                  # Unit tests
│   ├── test_agent.py
│   ├── test_browser.py
│   ├── test_database.py
│   └── test_pdf_generator.py
├── install.sh              # Mac/Linux installer
├── launch.sh               # Mac/Linux launcher
├── install.bat             # Windows installer
└── launch.bat              # Windows launcher
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

---

## 📝 Creating a Release

1. **Update version** in your code if needed
2. **Commit and push** all changes
3. **Create and push a tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
4. **GitHub Actions** will automatically:
   - Create a release package
   - Upload `amazon-fresh-fetch.zip`
   - Publish the release

---

## 🔧 Configuration

All configuration is in `config.py`:
- AI model names
- Database filename
- Browser session file
- UI styles
- Default meal plan prompt

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Run linter: `black . && pylint *.py`
6. Submit a pull request

---

## 📄 License

[Add your license here]

---

## 🆘 Support

For issues and questions, please [open an issue](https://github.com/geoffkip/Amazon-Fresh-Fetch/issues).
