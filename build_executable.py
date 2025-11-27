import PyInstaller.__main__
import os
import shutil
import streamlit

def build():
    print("🚀 Starting build process...")
    
    # Clean previous builds
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    # Define data files to include
    # Format: (source_path, dest_path)
    datas = [
        ("amazon_fresh_fetch.py", "."),
        ("ui.py", "."),
        ("prompts.py", "."),
        ("database.py", "."),
        ("agent.py", "."),
        ("workflow.py", "."),
        ("browser.py", "."),
        ("config.py", "."),
        ("utils.py", "."),
        ("pdf_generator.py", "."),
        (".env", ".") if os.path.exists(".env") else None,
    ]
    
    # Add Streamlit static files
    streamlit_path = os.path.dirname(streamlit.__file__)
    datas.append((os.path.join(streamlit_path, "static"), "streamlit/static"))
    datas.append((os.path.join(streamlit_path, "runtime"), "streamlit/runtime"))

    datas = [d for d in datas if d is not None]

    # Convert datas to PyInstaller format string
    add_data_args = []
    for src, dst in datas:
        sep = ";" if os.name == "nt" else ":"
        add_data_args.append(f"--add-data={src}{sep}{dst}")

    # PyInstaller arguments
    args = [
        "packaging/run_streamlit.py",  # Entry point
        "--name=AmazonFreshAgent",
        "--onefile",
        "--clean",
        "--additional-hooks-dir=packaging",
        "--hidden-import=streamlit",
        "--hidden-import=langchain",
        "--hidden-import=langchain_google_genai",
        "--hidden-import=langchain_core",
        "--hidden-import=langgraph",
        "--hidden-import=langgraph.graph",
        "--hidden-import=langgraph.checkpoint",
        "--hidden-import=langgraph.checkpoint.memory",
        "--hidden-import=dotenv",
        "--hidden-import=playwright",
        "--hidden-import=playwright.async_api",
        "--hidden-import=fpdf",
        "--hidden-import=pandas",
        "--hidden-import=sqlite3",
    ] + add_data_args

    print(f"📦 Running PyInstaller with args: {args}")
    
    PyInstaller.__main__.run(args)
    
    print("✅ Build complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build()
