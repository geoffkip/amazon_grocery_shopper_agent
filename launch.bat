@echo off
REM Amazon Fresh Fetch - Windows Launcher

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check if .env exists
if not exist ".env" (
    echo X .env file not found!
    echo Please run install.bat first
    pause
    exit /b 1
)

REM Launch the app
echo [*] Launching Amazon Fresh Fetch...
echo Opening in your browser...
echo.
echo Press Ctrl+C to stop the app
echo.

REM Open browser after a short delay
start /B timeout /t 2 /nobreak >nul && start http://localhost:8501

REM Start Streamlit
streamlit run amazon_fresh_fetch.py
