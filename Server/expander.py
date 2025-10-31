#!/usr/bin/env python3
import os
import json
import re
import time
import pyperclip
from pynput import keyboard
from pynput.keyboard import Controller, Key
from cryptography.fernet import Fernet

# ================= CONFIG =================
SNIPPET_FILE = "snippets.json"
KEY_FILE = "snippet_key.key"
TRIGGER_PATTERN = re.compile(r"--([A-Za-z0-9_]+)--")  # pattern to detect
PASTE_DELAY = 0.05  # delay between cmd/ctrl + v press

# ================= LOAD ENCRYPTION KEY =================
if not os.path.exists(KEY_FILE):
    print("❌ Key file not found!")
    exit(1)

key = open(KEY_FILE, "rb").read()
cipher = Fernet(key)

# ================= LOAD SNIPPETS =================
def load_snippets():
    if not os.path.exists(SNIPPET_FILE):
        return {}
    with open(SNIPPET_FILE, "r") as f:
        data = f.read().strip()
    if not data:
        return {}
    try:
        decrypted = cipher.decrypt(data.encode()).decode()
        return json.loads(decrypted)
    except Exception as e:
        print("❌ Failed to decrypt snippets:", e)
        return {}

# ================= CLIPBOARD PASTE FUNCTION =================
kb = Controller()

def paste_snippet(text):
    try:
        pyperclip.copy(text)
        if os.name == "nt":  # Windows
            with kb.pressed(keyboard.Key.ctrl):
                kb.press('v')
                kb.release('v')
        else:  # macOS/Linux
            with kb.pressed(keyboard.Key.cmd):
                kb.press('v')
                kb.release('v')
        time.sleep(PASTE_DELAY)
        print("✅ Snippet pasted via clipboard.")
    except Exception as e:
        print("❌ Clipboard paste error:", e)

# ================= KEYBOARD MONITOR =================
buffer = ""

def on_press(key):
    global buffer
    try:
        ch = key.char
    except AttributeError:
        if key == keyboard.Key.space:
            ch = " "
        elif key == keyboard.Key.enter:
            ch = "\n"
        elif key == keyboard.Key.tab:
            ch = "\t"
        elif key == keyboard.Key.backspace:
            if buffer:
                buffer = buffer[:-1]
            ch = None
        else:
            ch = None

    if ch is not None:
        buffer += ch

    # keep buffer reasonable
    if len(buffer) > 200:
        buffer = buffer[-200:]

    # search for trigger
    m = TRIGGER_PATTERN.search(buffer)
    if m:
        snippet_name = m.group(1)
        print(f"🔍 Trigger detected: '{snippet_name}'")
        snippets = load_snippets()
        if snippet_name in snippets:
            # Delete trigger from buffer (simulate backspaces)
            for _ in range(m.end() - m.start()):
                kb.press(Key.backspace)
                kb.release(Key.backspace)
                time.sleep(0.005)
            # Paste snippet
            paste_snippet(snippets[snippet_name]["code"])
        else:
            print(f"⚠️ Snippet '{snippet_name}' not found.")
        # remove matched text from buffer
        buffer = buffer[:m.start()] + buffer[m.end():]

# ================= MAIN =================
def main():
    print("👀 Snippet expander running. Type --<exam_text>-- to paste the snippet content.")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == "__main__":
    main()
