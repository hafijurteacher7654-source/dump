import pyautogui
import pytesseract
import cv2
import numpy as np
import requests
import re
import google.generativeai as genai
import os
from pynput import keyboard as kb
import tkinter as tk
import time

# ======================
# CONFIGURATION
# ======================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDKo5yMfZw74cY_XJB0Ng-LudnGcy_tpgQ")
MODEL_NAME = "models/gemini-1.5-flash"
SEARCH_CONFIDENCE_THRESHOLD = 0.5

genai.configure(api_key=GEMINI_API_KEY)

# ======================
# OCR & SEARCH HELPERS
# ======================
def clean_text(text):
    text = re.sub(r'[^A-Za-z0-9\s\?\.,:;()\[\]-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_question_and_options(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = [clean_text(l) for l in lines if len(l.strip()) > 2]

    question_candidates = [l for l in cleaned if '?' in l]
    if question_candidates:
        question = max(question_candidates, key=len)
        q_index = cleaned.index(question)
    else:
        question = max(cleaned, key=len) if cleaned else ""
        q_index = cleaned.index(question) if question else 0

    options = cleaned[q_index + 1: q_index + 6]
    if not options and q_index >= 1:
        options = cleaned[q_index - 4: q_index]

    return question, options

def search_google_answer(question, options):
    try:
        query = requests.utils.quote(question + " " + " ".join(options))
        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        text = res.text.lower()
        scores = {opt: text.count(opt.lower()) for opt in options}
        best_option = max(scores, key=scores.get) if scores else None
        confidence = (scores[best_option] / sum(scores.values())) if sum(scores.values()) else 0
        return best_option, confidence
    except:
        return None, 0.0

def ask_gemini(question, options):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"Question: {question}\nOptions: {options}\nPick correct option only."
        response = model.generate_content(prompt)
        answer = response.text.strip()
        for opt in options:
            if opt.lower() in answer.lower():
                return opt
        return answer
    except:
        return None

def move_cursor_to_answer(answer_text):
    try:
        screen = pyautogui.screenshot()
        img = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
        result = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        for i, word in enumerate(result["text"]):
            if answer_text.lower() in word.lower():
                x, y, w, h = result["left"][i], result["top"][i], result["width"][i], result["height"][i]
                pyautogui.moveTo(x + w // 2, y + h // 2, duration=0.3)
                print(f"➡️ Cursor moved to: {answer_text}")
                return True
        print(f"⚠️ Could not locate answer visually. Suggested: {answer_text}")
        return False
    except:
        return False

# ======================
# REGION SELECTION (macOS-safe)
# ======================
def select_region():
    selection_coords = {}

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.3)
    root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.config(cursor="cross")

    canvas = tk.Canvas(root, bg="gray")
    canvas.pack(fill=tk.BOTH, expand=True)

    start_x = start_y = 0
    rect = None
    overlay = None
    size_text = None

    def on_click(event):
        nonlocal start_x, start_y, rect, overlay, size_text
        start_x, start_y = event.x, event.y
        if rect: canvas.delete(rect)
        if overlay: canvas.delete(overlay)
        if size_text: canvas.delete(size_text)
        rect = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline="red", width=2)
        overlay = canvas.create_rectangle(start_x, start_y, start_x, start_y, fill="red", stipple="gray25")
        size_text = canvas.create_text(start_x, start_y - 15, text="", fill="white")

    def on_drag(event):
        nonlocal rect, overlay, size_text
        canvas.coords(rect, start_x, start_y, event.x, event.y)
        canvas.coords(overlay, start_x, start_y, event.x, event.y)
        width = abs(event.x - start_x)
        height = abs(event.y - start_y)
        canvas.itemconfig(size_text, text=f"{width} x {height}")
        canvas.coords(size_text, (start_x + event.x)//2, start_y - 15)

    def on_release(event):
        nonlocal root
        selection_coords['x1'] = min(start_x, event.x)
        selection_coords['y1'] = min(start_y, event.y)
        selection_coords['x2'] = max(start_x, event.x)
        selection_coords['y2'] = max(start_y, event.y)
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_click)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)

    root.mainloop()
    time.sleep(0.1)  # wait for overlay to go

    if selection_coords:
        x1, y1, x2, y2 = selection_coords['x1'], selection_coords['y1'], selection_coords['x2'], selection_coords['y2']
        screenshot = pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1))
        return screenshot
    else:
        return None

# ======================
# MAIN WORKFLOW
# ======================
def process_question():
    print("🎯 Draw rectangle around question → Release")
    roi = select_region()
    if roi is None:
        print("⚠️ No region selected")
        return

    text = pytesseract.image_to_string(roi)
    question, options = extract_question_and_options(text)
    print(f"❓ {question}")
    print(f"📋 {options}")

    if not question or len(options) < 2:
        print("⚠️ Could not detect options")
        return

    answer, confidence = search_google_answer(question, options)
    if answer and confidence >= SEARCH_CONFIDENCE_THRESHOLD:
        print(f"✅ Google suggests: {answer} ({confidence:.2f})")
        move_cursor_to_answer(answer)
    else:
        print(f"⚠️ Low confidence, using Gemini...")
        answer = ask_gemini(question, options)
        if answer:
            print(f"🤖 Gemini suggests: {answer}")
            move_cursor_to_answer(answer)
        else:
            print("❌ Could not determine answer")

# ======================
# HOTKEY LISTENER
# ======================
def on_press(key):
    if key == kb.Key.f8:
        # Tkinter overlay must run on main thread (so we call directly)
        process_question()
    elif key == kb.Key.esc:
        print("👋 Exiting...")
        return False

print("✅ Press F8 → draw rectangle → release. ESC to exit.")
with kb.Listener(on_press=on_press) as listener:
    listener.join()
