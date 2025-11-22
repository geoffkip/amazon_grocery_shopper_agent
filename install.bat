@echo off
REM Amazon Fresh Fetch - Windows Installer

echo ==========================================
echo   Amazon Fresh Fetch - Installation
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python is not installed!
    echo Please install Python 3.8 or higher from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

REM Display Python version
echo [OK] Found Python
python --version

REM Create virtual environment
echo.
echo [*] Creating virtual environment...
python -m venv .venv

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo [*] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install dependencies
echo.
echo [*] Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt --quiet

REM Install Playwright browsers
echo.
echo [*] Installing browser automation (Playwright)...
playwright install chromium

REM Setup .env file
echo.
if not exist ".env" (
    echo [*] Setting up API key...
    echo.
    echo Please enter your Google API Key
    echo (Get it from: https://makersuite.google.com/app/apikey)
    set /p api_key="API Key: "
    echo GOOGLE_API_KEY=!api_key! > .env
    echo [OK] API key saved to .env
) else (
    echo [i] .env file already exists, skipping API key setup
)

echo.
echo ==========================================
echo   [OK] Installation Complete!
echo ==========================================
echo.
echo To launch the app, run: launch.bat
echo Or double-click the launch.bat file
echo.
pause
