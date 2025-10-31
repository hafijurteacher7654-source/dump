from websocket_server import WebsocketServer
import threading

SNIPPETS = {}

def on_message(client, server, message):
    keyword = message.strip()
    if keyword in SNIPPETS:
        server.send_message(client, SNIPPETS[keyword])
    else:
        server.send_message(client, f"⚠️ No snippet found for '{keyword}'")

def on_new_client(client, server):
    print(f"✅ Client connected: {client['id']}")
    # Optional: send current snippet names
    server.send_message(client, "Available snippets: " + ", ".join(SNIPPETS.keys()))

def on_client_left(client, server):
    print(f"❌ Client disconnected: {client['id']}")

def ws_server_thread():
    server = WebsocketServer(host='0.0.0.0', port=8002, loglevel=0)  # fixed loglevel
    server.set_fn_new_client(on_new_client)
    server.set_fn_message_received(on_message)
    server.set_fn_client_left(on_client_left)
    print("🌐 Snippet server running on ws://localhost:8002")
    server.run_forever()

def main():
    threading.Thread(target=ws_server_thread, daemon=True).start()
    while True:
        print("\n--- Create New Snippet ---")
        name = input("Enter snippet name: ").strip()
        code = input("Enter snippet code: ").strip()
        SNIPPETS[name] = code
        print(f"✅ Snippet '{name}' saved. Connected clients will see updates automatically.")

if __name__ == "__main__":
    main()
