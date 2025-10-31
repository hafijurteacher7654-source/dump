import json
import threading
from websocket_server import WebsocketServer

# --------------------------
# Authentication
# --------------------------
AUTH_TOKEN = "mysecret123"

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
            print(f"⚠️ Unauthorized message from client {client['id']}")
            return
    except Exception as e:
        print(f"❗Error processing message from client {client['id']}: {e}")

# --------------------------
# Cursor control functions
# --------------------------
def change_client_cursor(cursor_type="arrow"):
    for client in server.clients:
        server.send_message(client, json.dumps({
            "token": AUTH_TOKEN,
            "action": "change_cursor",
            "cursor": cursor_type
        }))
    print(f"🖱️ Cursor changed to '{cursor_type}' on all clients")

def restore_client_cursor():
    for client in server.clients:
        server.send_message(client, json.dumps({
            "token": AUTH_TOKEN,
            "action": "restore_cursor"
        }))
    print("🖱️ Cursor restored on all clients")

# --------------------------
# Start WebSocket server
# --------------------------
def run_server():
    global server
    server = WebsocketServer(host='0.0.0.0', port=8002)
    server.set_fn_new_client(new_client)
    server.set_fn_client_left(client_left)
    server.set_fn_message_received(message_received)
    print("🌐 Cursor Control Server running on port 8002...")
    server.run_forever()

# --------------------------
# CLI Menu
# --------------------------
def main_menu():
    while True:
        print("\n=== 🖱️ Cursor Control Menu ===")
        print("1. Change Cursor")
        print("2. Restore Cursor")
        print("3. List Connected Clients")
        print("4. Exit")
        choice = input("Choose: ").strip()

        if choice == "1":
            ctype = input("Enter cursor (arrow, hand, cross, wait, uparrow): ").strip()
            change_client_cursor(ctype)
        elif choice == "2":
            restore_client_cursor()
        elif choice == "3":
            print(f"👥 Connected clients: {[c['id'] for c in server.clients]}")
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("❌ Invalid choice. Try again.")

# --------------------------
# Main entry
# --------------------------
if __name__ == "__main__":
    # Start server in background thread
    threading.Thread(target=run_server, daemon=True).start()
    print("🚀 Start ngrok in another terminal: ngrok tcp 8002")
    main_menu()