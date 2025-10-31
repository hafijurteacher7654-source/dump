import json
import os
import threading
import time
from websocket_server import WebsocketServer
from cryptography.fernet import Fernet

# --------------------------
# Config & Auth
# --------------------------
AUTH_TOKEN = "notsosecret123"
SNIPPET_FILE = "snippets.json"
KEY_FILE = "snippet_key.key"

# --------------------------
# Clipboard support (optional)
# --------------------------
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    print("⚠ pyperclip not installed. Clipboard disabled")

# --------------------------
# Encryption
# --------------------------
def load_or_generate_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    return key

key = load_or_generate_key()
cipher = Fernet(key)

# --------------------------
# Snippet functions
# --------------------------
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
        except Exception:
            print("⚠ Error decrypting snippet file")
            return {}

def save_snippets(snippets):
    encrypted = cipher.encrypt(json.dumps(snippets, indent=2).encode()).decode()
    with open(SNIPPET_FILE, "w") as f:
        f.write(encrypted)

def multiline_input(prompt="Enter code (type END alone to finish):"):
    print(prompt)
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

# --------------------------
# Client management
# --------------------------
connected_clients = {}  # client_id -> client dict
clients_lock = threading.Lock()
server = None

def new_client(client, server_instance):
    ip, port = client['address']
    print(f"⚡ New connection from {ip}:{port}, waiting for client_id...")

def client_left(client, server_instance):
    with clients_lock:
        for cid, cobj in list(connected_clients.items()):
            if cobj == client:
                del connected_clients[cid]
                print(f"❌ Client '{cid}' disconnected")

def message_received(client, server_instance, message):
    try:
        data = json.loads(message)
        token = data.get("token")
        if token != AUTH_TOKEN:
            server_instance.send_message(client, json.dumps({"type":"error","msg":"Unauthorized"}))
            return

        client_id = data.get("client_id")
        action = data.get("action")
        snippet_name = data.get("snippet")

        # -------------------- Register client --------------------
        if action == "register_client" and client_id:
            with clients_lock:
                connected_clients[client_id] = client
            print(f"✅ Client '{client_id}' registered")
            server_instance.send_message(client, json.dumps({"type":"info","msg":f"Registered as {client_id}"}))
            return

        # -------------------- Snippet request --------------------
        if snippet_name:
            snippets = load_snippets()
            if snippet_name in snippets:
                snippet = snippets[snippet_name]
                server_instance.send_message(client, json.dumps({
                    "type": "snippet",
                    "name": snippet_name,
                    "code": snippet["code"]
                }))
                print(f"🚀 Sent snippet '{snippet_name}' to '{client_id}'")
            else:
                server_instance.send_message(client, json.dumps({
                    "type":"error",
                    "msg": f"Snippet '{snippet_name}' not found"
                }))

        # -------------------- Cursor commands --------------------
        if action == "change_cursor":
            cursor_type = str(data.get("cursor","1"))
            with clients_lock:
                for cl in connected_clients.values():
                    server_instance.send_message(cl, json.dumps({
                        "token": AUTH_TOKEN,
                        "action": "change_cursor",
                        "cursor": cursor_type
                    }))
            # auto-restore in 2 sec
            threading.Thread(target=lambda: (time.sleep(2), restore_cursor()), daemon=True).start()

        if action == "restore_cursor":
            restore_cursor()

    except Exception as e:
        print(f"❗Error processing message: {e}")

def restore_cursor():
    with clients_lock:
        for cl in connected_clients.values():
            server.send_message(cl, json.dumps({
                "token": AUTH_TOKEN,
                "action": "restore_cursor"
            }))
    print("🖱 Cursor restored on all clients")

def disconnect_all_clients():
    with clients_lock:
        for cid, cl in list(connected_clients.items()):
            server._unregister(cl)
            print(f"🛑 Disconnected client '{cid}'")
        connected_clients.clear()

# --------------------------
# WebSocket server
# --------------------------
def run_server():
    global server
    server = WebsocketServer(host='0.0.0.0', port=8002)
    server.set_fn_new_client(new_client)
    server.set_fn_client_left(client_left)
    server.set_fn_message_received(message_received)
    print("🌐 WebSocket Server running on port 8002...")
    server.run_forever()

threading.Thread(target=run_server, daemon=True).start()

# --------------------------
# CLI Menus
# --------------------------
def snippet_menu():
    while True:
        print("\n=== Snippet Management ===")
        print("1. Add Snippet")
        print("2. List Snippets")
        print("3. View & Copy Snippet")
        print("4. Delete Snippet")
        print("0. Back")
        choice = input("Choose: ").strip()
        snippets = load_snippets()

        if choice=="1":
            name = input("Snippet name: ").strip()
            code = multiline_input("Enter code (type END alone to finish):")
            snippets[name] = {"code": code}
            save_snippets(snippets)
            print(f"✅ Snippet '{name}' saved.")
        elif choice=="2":
            if not snippets:
                print("⚠ No snippets found.")
            else:
                for idx, name in enumerate(snippets,1):
                    print(f"{idx}. {name}")
        elif choice=="3":
            name = input("Enter snippet name: ").strip()
            if name in snippets:
                code = snippets[name]['code']
                print(f"\n💻 {name}:\n{'-'*40}\n{code}\n{'-'*40}")
                if CLIPBOARD_AVAILABLE:
                    pyperclip.copy(code)
                    print("📋 Copied to clipboard!")
            else:
                print("❌ Not found.")
        elif choice=="4":
            name = input("Enter snippet name: ").strip()
            if name in snippets:
                del snippets[name]
                save_snippets(snippets)
                print(f"🗑 Deleted '{name}'")
        elif choice=="0":
            break

def cursor_menu():
    while True:
        print("\n=== Cursor Menu ===")
        print("1. Change Cursor")
        print("2. Restore Cursor")
        print("3. List Clients")
        print("4. Disconnect All Clients")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice=="1":
            ctype = input("Enter cursor (1-5, a-e): ").strip()
            with clients_lock:
                for cl in connected_clients.values():
                    server.send_message(cl, json.dumps({
                        "token": AUTH_TOKEN,
                        "action": "change_cursor",
                        "cursor": ctype
                    }))
            threading.Thread(target=lambda: (time.sleep(2), restore_cursor()), daemon=True).start()
        elif choice=="2":
            restore_cursor()
        elif choice=="3":
            with clients_lock:
                if not connected_clients:
                    print("⚠ No clients connected.")
                else:
                    for cid in connected_clients:
                        print(f"• {cid}")
        elif choice=="4":
            disconnect_all_clients()
        elif choice=="0":
            break

def main_menu():
    while True:
        print("\n=== Main Menu ===")
        print("1. Snippet Management")
        print("2. Cursor Management")
        print("0. Quit")
        choice = input("Choose: ").strip()

        if choice=="1": snippet_menu()
        elif choice=="2": cursor_menu()
        elif choice=="0":
            print("Exiting...")
            break
        else:
            print("❌ Invalid choice.")

if __name__=="__main__":
    main_menu()
