#!/usr/bin/env python3
import json
import os
import threading
from websocket_server import WebsocketServer
from cryptography.fernet import Fernet

# --------------------------
# Config & Files
# --------------------------
AUTH_TOKEN = "notsosecret123"
SNIPPET_FILE = "snippets.json"
KEY_FILE = "snippet_key.key"

# --------------------------
# Global server handle (so helper functions can access it)
# --------------------------
server = None

# --------------------------
# Encryption key
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
# Snippet management
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
            print("⚠️ Error decrypting snippet file")
            return {}

def save_snippets(snippets):
    encrypted = cipher.encrypt(json.dumps(snippets, indent=2).encode()).decode()
    with open(SNIPPET_FILE, "w") as f:
        f.write(encrypted)

# --------------------------
# WebSocket server & clients
# --------------------------
connected_clients = {}  # client_id -> client_object
client_lock = threading.Lock()

def new_client(client, server_arg):
    ip, port = client['address']
    print(f"⚡ New connection from {ip}:{port}, waiting for client_id...")

def client_left(client, server_arg):
    with client_lock:
        remove = [cid for cid, c in connected_clients.items() if c == client]
        for cid in remove:
            del connected_clients[cid]
            print(f"❌ Client '{cid}' disconnected")

def message_received(client, server_arg, message):
    try:
        data = json.loads(message)
        token = data.get("token")
        client_id = data.get("client_id")

        if token != AUTH_TOKEN:
            server_arg.send_message(client, json.dumps({"type":"error","msg":"Unauthorized"}))
            return

        # Register client
        if data.get("action") == "register_client" and client_id:
            with client_lock:
                if client_id in connected_clients:
                    # Replace previous client object
                    old_client = connected_clients[client_id]
                    try:
                        server_arg._unregister(old_client)
                    except Exception:
                        pass
                    print(f"⚠ Replaced existing client '{client_id}'")
                connected_clients[client_id] = client
                print(f"✅ Client '{client_id}' registered")
            server_arg.send_message(client, json.dumps({"type":"info","msg":f"Registered as {client_id}"}))
            return

        # Ensure registered
        with client_lock:
            if not client_id or client_id not in connected_clients:
                server_arg.send_message(client, json.dumps({"type":"error","msg":"Client not registered"}))
                return

        # Snippet request
        snippet_name = data.get("snippet")
        if snippet_name:
            snippets = load_snippets()
            if snippet_name in snippets:
                snippet = snippets[snippet_name]
                server_arg.send_message(client, json.dumps({
                    "type":"snippet",
                    "name": snippet_name,
                    "code": snippet["code"]
                }))
                print(f"🚀 Sent snippet '{snippet_name}' to '{client_id}'")
            else:
                server_arg.send_message(client, json.dumps({
                    "type":"error",
                    "msg": f"Snippet '{snippet_name}' not found"
                }))

        # Cursor commands
        if data.get("action") == "change_cursor":
            ctype = str(data.get("cursor","1"))
            with client_lock:
                for cl in connected_clients.values():
                    server_arg.send_message(cl, json.dumps({
                        "token": AUTH_TOKEN,
                        "action":"change_cursor",
                        "cursor": ctype
                    }))
            # Auto restore in 2 sec (use a thread to avoid blocking)
            threading.Thread(target=lambda: (threading.Event().wait(2), restore_cursor()), daemon=True).start()
            print(f"🖱 Cursor changed to '{ctype}' on all clients")

        if data.get("action") == "restore_cursor":
            restore_cursor()

    except Exception as e:
        print("❗Error processing message:", e)

def restore_cursor():
    global server
    with client_lock:
        if server is None:
            print("⚠️ restore_cursor called but server not initialized")
            return
        for cl in connected_clients.values():
            try:
                server.send_message(cl, json.dumps({
                    "token": AUTH_TOKEN,
                    "action":"restore_cursor"
                }))
            except Exception as ex:
                print("⚠️ Failed to send restore to a client:", ex)
        print("🖱 Cursor restored on all clients")

# --------------------------
# WebSocket server thread
# --------------------------
def run_server(host='0.0.0.0', port=8002):
    global server
    server = WebsocketServer(host=host, port=port)
    server.set_fn_new_client(new_client)
    server.set_fn_client_left(client_left)
    server.set_fn_message_received(message_received)
    print(f"🌐 Snippet+Cursor WebSocket Server running on {host}:{port}...")
    try:
        server.run_forever()
    except KeyboardInterrupt:
        print("🌐 WebSocket server shutting down...")

# --------------------------
# CLI Menu
# --------------------------
def multiline_input(prompt="Enter code (type END alone to finish):"):
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

def add_snippet():
    name = input("Snippet name: ").strip()
    code = multiline_input()
    snippets = load_snippets()
    snippets[name] = {"code": code}
    save_snippets(snippets)
    print(f"✅ Snippet '{name}' saved.")

def list_snippets():
    snippets = load_snippets()
    if not snippets:
        print("⚠️ No snippets found")
        return
    print("📜 Available snippets:")
    for name in snippets:
        print(f"• {name}")

def view_snippet():
    name = input("Enter snippet name: ").strip()
    snippets = load_snippets()
    if name in snippets:
        print("-"*40)
        print(snippets[name]["code"])
        print("-"*40)
    else:
        print("❌ Snippet not found.")

def delete_snippet():
    name = input("Enter snippet name: ").strip()
    snippets = load_snippets()
    if name in snippets:
        del snippets[name]
        save_snippets(snippets)
        print(f"🗑 Deleted '{name}'")
    else:
        print("❌ Snippet not found.")

def main_menu():
    threading.Thread(target=run_server, daemon=True).start()
    while True:
        print("\n=== Snippet Server Menu ===")
        print("1. Add Snippet")
        print("2. List Snippets")
        print("3. View Snippet")
        print("4. Delete Snippet")
        print("5. Exit")
        choice = input("Choose: ").strip()
        if choice=="1": add_snippet()
        elif choice=="2": list_snippets()
        elif choice=="3": view_snippet()
        elif choice=="4": delete_snippet()
        elif choice=="5": break
        else: print("❌ Invalid choice")

# keep compatibility: define main() to call main_menu()
def main():
    main_menu()

if __name__=="__main__":
    main()
