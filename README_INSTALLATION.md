# Amazon Fresh Fetch - User Installation Guide

## 📋 Requirements

- **macOS/Linux**: Python 3.8+ installed
- **Windows**: Python 3.8+ installed (with "Add to PATH" enabled)
- Internet connection for initial setup
- Google API Key (get from: https://makersuite.google.com/app/apikey)

---

## 🍎 macOS/Linux Installation

### First-Time Setup:

1. **Extract the ZIP file** you downloaded
2. **Open Terminal** in the extracted folder:
   - Right-click the folder → "New Terminal at Folder" (Mac)
   - Or navigate using: `cd /path/to/amazon_agent`
3. **Run the installer**:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
4. **Enter your Google API Key** when prompted
5. **Wait for installation** (~2-3 minutes)

### Running the App:

**Option 1**: Double-click `launch.sh`  
**Option 2**: Run in Terminal:
```bash
./launch.sh
```

The app will open automatically in your browser!

---

## 🪟 Windows Installation

### First-Time Setup:

1. **Extract the ZIP file** you downloaded
2. **Double-click `install.bat`**
3. **Enter your Google API Key** when prompted
4. **Wait for installation** (~2-3 minutes)
5. **Press any key** to close the installer

### Running the App:

**Double-click `launch.bat`**

The app will open automatically in your browser!

---

## 🔑 Getting Your Google API Key

1. Go to: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Paste it when the installer asks for it

---

## ❓ Troubleshooting

### "Python is not installed"
**Mac**: Install from https://www.python.org/downloads/  
**Windows**: Install from https://www.python.org/downloads/ (check "Add Python to PATH")

### "Permission denied" (Mac/Linux)
Run: `chmod +x install.sh launch.sh`

### App won't start
1. Make sure you ran `install.sh` / `install.bat` first
2. Check that `.env` file exists with your API key

### Browser doesn't open automatically
Manually open: http://localhost:8501

---

## 📝 Notes

- **First run**: May take a moment to load
- **Data storage**: All meal plans saved in `agent_data.db`
- **Browser sessions**: Stored in `amazon_session.json`
- **Updates**: Re-run installer to update dependencies

---

## 🆘 Need Help?

- Check that Python 3.8+ is installed: `python3 --version` (Mac/Linux) or `python --version` (Windows)
- Ensure internet connection during installation
- Make sure you have your Google API key ready

---

Enjoy your automated meal planning! 🥕
