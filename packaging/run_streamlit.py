import os
import sys
import streamlit.web.cli as stcli

def resolve_path(path):
    if getattr(sys, "frozen", False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)

    return os.path.join(basedir, path)

if __name__ == "__main__":
    # Force Playwright to look in the system cache, not the temp bundle directory
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

    # Set the path to the main app file
    # When frozen, the app file will be in the root of the bundle
    app_path = resolve_path("amazon_fresh_fetch.py")
    
    # Set up arguments for streamlit run
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
    ]
    
    sys.exit(stcli.main())
