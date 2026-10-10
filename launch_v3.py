"""
Launcher for Francine Screener V3 — uses streamlit web CLI directly.
"""
import os
import sys
import threading
import webbrowser
import time

PORT = 8502

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_PY = os.path.join(BASE_DIR, "app.py")


def open_browser_delayed():
    time.sleep(4)
    webbrowser.open(f"http://localhost:{PORT}")


def main():
    if not os.path.exists(APP_PY):
        print(f"ERROR: app.py not found at {APP_PY}")
        input("\nPress Enter to close this window...")
        sys.exit(1)

    print(f"Starting Francine Screener V3...")
    print(f"Open http://localhost:{PORT} in your browser")
    print(f"Press Ctrl+C in this window to stop the app.\n")

    threading.Thread(target=open_browser_delayed, daemon=True).start()

    # Use streamlit's web CLI — same as "streamlit run app.py"
    sys.argv = [
        "streamlit",
        "run",
        APP_PY,
        "--server.port", str(PORT),
        "--server.headless", "true",
        "--server.address", "localhost",
        "--global.developmentMode", "false",
        "--browser.gatherUsageStats", "false",
        "--client.toolbarMode", "minimal",
    ]

    from streamlit.web import cli as stcli
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()