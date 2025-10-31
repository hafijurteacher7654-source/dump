import os
import time
import requests
import pytesseract
import cv2
import numpy as np
from cryptography.fernet import Fernet
import json
import re
# ========= CONFIG =========
GITHUB_TOKEN = "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"
REPO_OWNER = "gtmrahul"
REPO_NAME = "cobra_ss"
FOLDER = "screenshots" 
CHECK_INTERVAL = 10           # seconds between checks
SNIPPET_NAME = "paste"    # fixed snippet name
SNIPPET_FILE = "snippets.json"
KEY_FILE = "snippet_key.key"

# ========= LOAD/GENERATE ENCRYPTION KEY =========
def load_or_generate_key():
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE, "rb").read()
    key = Fernet.generate_key()
    open(KEY_FILE, "wb").write(key)
    return key

key = load_or_generate_key()
cipher = Fernet(key)

def load_snippets():
    if not os.path.exists(SNIPPET_FILE):
        return {}
    data = open(SNIPPET_FILE).read().strip()
    if not data:
        return {}
    try:
        dec = cipher.decrypt(data.encode()).decode()
        return json.loads(dec)
    except Exception:
        print("⚠️ Corrupt snippet file; recreating.")
        return {}

def save_snippets(snips):
    enc = cipher.encrypt(json.dumps(snips, indent=2).encode()).decode()
    open(SNIPPET_FILE, "w").write(enc)

# ========= OCR HELPERS =========
def image_from_github_content(url):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        img_data = np.frombuffer(r.content, np.uint8)
        return cv2.imdecode(img_data, cv2.IMREAD_COLOR)
    print("❌ Failed to fetch image:", r.status_code)
    return None

def extract_text_from_img(img):
    text = pytesseract.image_to_string(img)
    return text.strip()

# ========= GITHUB HELPERS =========
def list_screenshots():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FOLDER}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        files = [f for f in r.json() if f["name"].endswith(".png")]
        return sorted(files, key=lambda f: f["name"])
    else:
        print("❌ GitHub API error:", r.status_code, r.text)
        return []

# ========= MAIN LOOP =========
def main():
    seen = set()
    print("👀 Watching GitHub for new screenshots every 10s...")
    while True:
        try:
            files = list_screenshots()
            for f in files:
                if f["sha"] not in seen:
                    print(f"🆕 New screenshot detected: {f['name']}")
                    img = image_from_github_content(f["download_url"])
                    if img is not None:
                        text = extract_text_from_img(img)
                        snippets = load_snippets()
                        snippets[SNIPPET_NAME] = {"description": "Auto OCR snippet", "code": text}
                        save_snippets(snippets)
                        print(f"✅ Snippet '{SNIPPET_NAME}' updated. You can now expand it manually.")
                    seen.add(f["sha"])
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("👋 Exiting watcher.")
            break
        except Exception as e:
            print("❗Error:", e)
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
