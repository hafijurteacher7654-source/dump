#!/usr/bin/env python3
"""
Fast screenshot uploader (in-memory) on macOS.
Hotkey: Cmd + Option + X
Uploads to GitHub repo in "screenshots" folder, no local files saved.

Requirements:
    pip install pyautogui pynput requests
Grant Terminal / Python accessibility + screen recording in macOS settings.
"""

import io
import base64
import datetime
import threading
import traceback
import requests
from pynput.keyboard import GlobalHotKeys
import pyautogui

# ---------------- CONFIG ----------------
GITHUB_TOKEN = "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"
REPO_OWNER = "gtmrahul"
REPO_NAME = "test"
REPO_FOLDER = "ss-rahul"
COMMIT_MSG_PREFIX = "Add screenshot"
HOTKEY = "<cmd>+<alt_l>+x"
RESIZE_FACTOR = 0.5   # reduce screenshot size to 50% (adjust 0.1–1)
JPEG_QUALITY = 75     # compression for faster upload (optional)
# ----------------------------------------

GITHUB_API = "https://api.github.com"

# ---------------- FUNCTIONS ----------------

def take_screenshot_bytes():
    """Return compressed JPEG bytes (in-memory)."""
    img = pyautogui.screenshot()

    # Convert RGBA to RGB for JPEG compatibility
    if img.mode == "RGBA":
        img = img.convert("RGB")

    if RESIZE_FACTOR < 1:
        img = img.resize((int(img.width * RESIZE_FACTOR), int(img.height * RESIZE_FACTOR)))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def upload_to_github(filename, b64content):
    """Create or update file on GitHub."""
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{REPO_FOLDER}/{filename}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {"message": f"{COMMIT_MSG_PREFIX} {filename}", "content": b64content}

    # Check if file exists
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    return r.status_code, r.text

def take_and_upload_screenshot():
    """Capture screenshot and send to GitHub (thread-safe)."""
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"screenshot_{timestamp}.jpg"

    try:
        img_bytes = take_screenshot_bytes()
        b64content = base64.b64encode(img_bytes).decode()
    except Exception as e:
        print(f"[ERROR] Screenshot capture failed: {e}")
        traceback.print_exc()
        return

    try:
        status, text = upload_to_github(filename, b64content)
        if status in (200, 201):
            print(f"[{timestamp}] ✅ Uploaded {filename} to GitHub!")
        else:
            print(f"[{timestamp}] ❌ Upload failed: {status} {text}")
    except Exception as e:
        print(f"[ERROR] GitHub upload failed: {e}")
        traceback.print_exc()

def on_hotkey_triggered():
    # Run in separate thread so hotkey is responsive
    threading.Thread(target=take_and_upload_screenshot, daemon=True).start()

# ---------------- MAIN ----------------

def main():
    print(f"Listening for hotkey {HOTKEY} — press to capture & upload screenshot.")
    print("Press Ctrl+C in Terminal to exit.\n")
    hotkeys = {HOTKEY: on_hotkey_triggered}

    with GlobalHotKeys(hotkeys) as h:
        try:
            h.join()
        except KeyboardInterrupt:
            print("Exiting on user interrupt.")

if __name__ == "__main__":
    main()
