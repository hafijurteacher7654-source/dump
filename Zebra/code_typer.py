#!/usr/bin/env python3
import websocket
import json
import threading
import time
import queue
import re
from pynput import keyboard
from pynput.keyboard import Controller

# --------------------------
# Configuration (edit these)
# --------------------------
# Use ws://localhost:8002 for local testing. Use wss://your-public-url for internet (server must support TLS).
WS_URL = "wss://manuela-corporational-nonconsumptively.ngrok-free.dev"
AUTH_TOKEN = "mysecret123"

# Trigger detection: {snippet_name} where name is letters, numbers, underscore
DETECT_PATTERN = re.compile(r"/([A-Za-z0-9_]+)\\")


# Typing speed: seconds per character. 0.01 is fast; increase if characters drop.
TYPING_DELAY = 0.01

# Buffer max length (characters to keep for detection)
BUFFER_MAX = 200

# If True, also watch clipboard for triggers (copy {name} then press nothing, it will detect).
CLIPBOARD_MODE = False

# Backoff for reconnects (seconds)
RECONNECT_BASE = 1.0
RECONNECT_MAX = 30.0

# --------------------------
# Globals & primitives
# --------------------------
kb = Controller()
send_queue = queue.Queue()  # holds snippet names to request
connected_flag = threading.Event()
ws_app = None
ws_lock = threading.Lock()  # protect access when sending

# --------------------------
# WebSocket handling
# --------------------------
def make_ws_app(url):
    def on_open(ws):
        print("✅ WebSocket connected")
        connected_flag.set()

    def on_message(ws, message):
        try:
            data = json.loads(message)
        except Exception as e:
            print("Received non-JSON message:", message)
            return

        if data.get("type") == "snippet":
            name = data.get("name")
            code = data.get("code", "")
            print(f"→ Received snippet '{name}' (length {len(code)}). Typing...")
            type_snippet(code)
        elif data.get("type") == "error":
            print("⚠️ Server error:", data.get("msg"))
        else:
            # unknown message types may be ignored or logged
            pass

    def on_error(ws, error):
        print("WebSocket error:", error)

    def on_close(ws, code, reason):
        print("🔌 WebSocket closed", code, reason)
        connected_flag.clear()

    return websocket.WebSocketApp(url,
                                 on_open=on_open,
                                 on_message=on_message,
                                 on_error=on_error,
                                 on_close=on_close)

def ws_runner(url):
    """Run WSApp with auto-reconnect and backoff."""
    global ws_app
    backoff = RECONNECT_BASE
    while True:
        try:
            ws_app = make_ws_app(url)
            # run_forever blocks until closed; set ping_interval to keep connection alive
            ws_app.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e:
            print("WebSocket thread exception:", e)
        connected_flag.clear()
        print(f"Reconnecting in {backoff:.1f}s...")
        time.sleep(backoff)
        backoff = min(backoff * 1.8, RECONNECT_MAX)

# --------------------------
# Send worker: consumes send_queue and requests snippets from server
# --------------------------
def send_worker():
    while True:
        name = send_queue.get()  # blocking
        if name is None:
            break  # sentinel to exit
        payload = json.dumps({"token": AUTH_TOKEN, "snippet": name})
        # Try sending; if not connected, wait until connected (with timeout) and retry
        while True:
            if connected_flag.is_set() and ws_app is not None:
                try:
                    with ws_lock:
                        ws_app.send(payload)
                    # sent successfully
                    break
                except Exception as e:
                    print("Send failed (will retry):", e)
                    connected_flag.clear()
            # wait for connection to re-establish
            # wake up periodically to re-check
            time.sleep(0.2)

# --------------------------
# Typing routine (types into focused app)
# --------------------------
def type_snippet(code):
    """
    Types a code snippet character-by-character with **no indentation**.
    Every line starts at column 0 (left-aligned) in the editor.
    """
    try:
        kb = keyboard.Controller()

        # Normalize line endings
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        lines = code.split('\n')

        for line in lines:
            # Remove all tabs or leading spaces
            stripped_line = line.lstrip()

            # Type the line
            for ch in stripped_line:
                kb.type(ch)
                time.sleep(TYPING_DELAY)

            # Press Enter at the end of the line
            kb.press(keyboard.Key.enter)
            kb.release(keyboard.Key.enter)
            time.sleep(TYPING_DELAY)

        print("✅ Snippet typed left-aligned (no indentation).")

    except Exception as e:
        print("Typing error:", e)

# --------------------------
# Keyboard monitor: detect {snippet_name} typed by user
# --------------------------
def monitor_typing():
    buffer = ""
    def on_press(key):
        nonlocal buffer
        try:
            ch = key.char
        except AttributeError:
            # convert some special keys
            if key == keyboard.Key.space:
                ch = " "
            elif key == keyboard.Key.enter:
                ch = "\n"
            elif key == keyboard.Key.tab:
                ch = "\t"
            elif key == keyboard.Key.backspace:
                # remove last char from buffer
                if buffer:
                    buffer = buffer[:-1]
                ch = None
            else:
                ch = None

        if ch is not None:
            buffer += ch

        # keep buffer length bounded
        if len(buffer) > BUFFER_MAX:
            buffer = buffer[-BUFFER_MAX:]

        # search for trigger
        m = DETECT_PATTERN.search(buffer)
        if m:
            name = m.group(1)
            print(f"Detected trigger: {{{name}}} -> requesting snippet")
            send_queue.put(name)
            # remove the matched text from buffer so it won't retrigger immediately
            buffer = buffer[:m.start()] + buffer[m.end():]

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# --------------------------
# Clipboard watcher (optional)
# --------------------------
def clipboard_watcher():
    # Import locally to avoid dependency if disabled
    try:
        import pyperclip
    except Exception:
        print("pyperclip not installed; clipboard mode unavailable")
        return

    last = None
    while True:
        try:
            current = pyperclip.paste()
            if current != last:
                last = current
                m = DETECT_PATTERN.search(current)
                if m:
                    name = m.group(1)
                    print(f"Clipboard trigger detected: {{{name}}}")
                    send_queue.put(name)
        except Exception as e:
            print("Clipboard watcher error:", e)
        time.sleep(0.3)

# --------------------------
# Entrypoint
# --------------------------
def main():
    print("Starting CodeTyper client")
    print("WS_URL:", WS_URL)
    print("Typing delay:", TYPING_DELAY, "s/char")
    # Start websocket thread
    t_ws = threading.Thread(target=ws_runner, args=(WS_URL,), daemon=True)
    t_ws.start()
    # Start sender worker
    t_sender = threading.Thread(target=send_worker, daemon=True)
    t_sender.start()
    # Start clipboard watcher if enabled
    if CLIPBOARD_MODE:
        t_clip = threading.Thread(target=clipboard_watcher, daemon=True)
        t_clip.start()
    # Start keyboard monitor (blocking)
    try:
        monitor_typing()
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        send_queue.put(None)  # stop sender
        time.sleep(0.2)

if __name__ == "__main__":
    main()
