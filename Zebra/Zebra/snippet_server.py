import json
import os
from cryptography.fernet import Fernet
from websocket_server import WebsocketServer

# --------------------------
# File paths and auth
# --------------------------
SNIPPET_FILE = "snippets.json"
KEY_FILE = "snippet_key.key"
AUTH_TOKEN = "mysecret123"

# --------------------------
# Encryption key
# --------------------------
def load_or_generate_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
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
            print("⚠️ Error decrypting snippet file, creating new.")
            return {}

def save_snippets(snippets):
    encrypted = cipher.encrypt(json.dumps(snippets, indent=2).encode()).decode()
    with open(SNIPPET_FILE, "w") as f:
        f.write(encrypted)

# --------------------------
# WebSocket handlers
# --------------------------
def new_client(client, server):
    print(f"✅ Client {client['id']} connected")

def client_left(client, server):
    print(f"❌ Client {client['id']} disconnected")

def message_received(client, server, message):
    try:
        data = json.loads(message)
        token = data.get("token")
        if token != AUTH_TOKEN:
            server.send_message(client, json.dumps({"type": "error", "msg": "Unauthorized"}))
            return

        snippet_name = data.get("snippet")
        snippets = load_snippets()

        if snippet_name in snippets:
            snippet = snippets[snippet_name]
            server.send_message(client, json.dumps({
                "type": "snippet",
                "name": snippet_name,
                "code": snippet["code"]
            }))
            print(f"🚀 Sent snippet '{snippet_name}'")
        else:
            server.send_message(client, json.dumps({
                "type": "error",
                "msg": f"Snippet '{snippet_name}' not found"
            }))

    except Exception as e:
        print(f"❗Error processing message: {e}")

# --------------------------
# Snippet input utilities
# --------------------------
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
# CLI Menu
# --------------------------
def add_snippet():
    name = input("Snippet name: ").strip()
    desc = input("Description: ").strip()
    code = multiline_input()
    snippets = load_snippets()
    snippets[name] = {"description": desc, "code": code}
    save_snippets(snippets)
    print(f"✅ Snippet '{name}' saved successfully!")

def list_snippets():
    snippets = load_snippets()
    if not snippets:
        print("⚠️ No snippets found.")
        return
    print("\n📜 Available Snippets:")
    for name, data in snippets.items():
        print(f"• {name} — {data['description']}")

def view_snippet():
    name = input("Enter snippet name: ").strip()
    snippets = load_snippets()
    if name in snippets:
        print(f"\n📘 Snippet: {name}")
        print(f"📝 Description: {snippets[name]['description']}")
        print("💻 Code:\n" + "-" * 40)
        print(snippets[name]['code'])
        print("-" * 40)
    else:
        print("❌ Snippet not found.")

def delete_snippet():
    name = input("Enter snippet name to delete: ").strip()
    snippets = load_snippets()
    if name in snippets:
        del snippets[name]
        save_snippets(snippets)
        print(f"🗑️ Deleted snippet '{name}'")
    else:
        print("❌ Snippet not found.")

# --------------------------
# WebSocket server
# --------------------------
def run_server():
    server = WebsocketServer(host='0.0.0.0', port=8002)
    server.set_fn_new_client(new_client)
    server.set_fn_client_left(client_left)
    server.set_fn_message_received(message_received)
    print("🌐 Snippet WebSocket Server running on port 8002...")
    server.run_forever()

# --------------------------
# Main menu loop
# --------------------------
def main():
    import threading
    threading.Thread(target=run_server, daemon=True).start()

    while True:
        print("\n=== 🧩 Snippet Server Menu ===")
        print("1. Add Snippet")
        print("2. List Snippets")
        print("3. View Snippet")
        print("4. Delete Snippet")
        print("5. Exit")
        choice = input("Choose: ").strip()

        if choice == "1":
            add_snippet()
        elif choice == "2":
            list_snippets()
        elif choice == "3":
            view_snippet()
        elif choice == "4":
            delete_snippet()
        elif choice == "5":
            break
        else:
            print("❌ Invalid choice. Try again.")

if __name__ == "__main__":
    main()
