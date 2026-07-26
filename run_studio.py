import os
import sys
import webbrowser
import time
import subprocess

def launch_studio():
    print("==================================================")
    print(" 🚀 Launching AI Instagram Studio Web Dashboard")
    print(" 🌐 URL: http://localhost:5000")
    print("==================================================\n")

    # Open browser after 1.5 seconds
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:5000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # Launch app.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, "app.py"])

if __name__ == "__main__":
    launch_studio()
