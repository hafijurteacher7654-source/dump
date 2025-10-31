import json
import os
from tkinter import *
from tkinter import messagebox, scrolledtext
from cryptography.fernet import Fernet
from websocket_server import WebsocketServer
import threading

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
# WebSocket Handlers
# --------------------------
def new_client(client, server):
    print(f"✅ Client {client['id']} connected")

def client_left(client, server):
    print(f"❌ Client {client['id']} disconnected")

def message_received(client, server, message):
    import json
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

def run_server():
    server = WebsocketServer(host='0.0.0.0', port=8002)
    server.set_fn_new_client(new_client)
    server.set_fn_client_left(client_left)
    server.set_fn_message_received(message_received)
    print("🌐 Snippet WebSocket Server running on port 8002...")
    server.run_forever()

# --------------------------
# GUI Functions
# --------------------------
def refresh_list():
    listbox.delete(0, END)
    snippets = load_snippets()
    for name in snippets.keys():
        listbox.insert(END, name)

def add_snippet():
    name = name_entry.get().strip()
    desc = desc_entry.get().strip()
    code = code_text.get("1.0", END).strip()
    if not name or not code:
        messagebox.showwarning("Warning", "Snippet name and code required.")
        return
    snippets = load_snippets()
    snippets[name] = {"description": desc, "code": code}
    save_snippets(snippets)
    refresh_list()
    messagebox.showinfo("Success", f"Snippet '{name}' saved successfully!")

def view_snippet():
    selection = listbox.curselection()
    if not selection:
        messagebox.showwarning("Warning", "Select a snippet first.")
        return
    name = listbox.get(selection[0])
    snippets = load_snippets()
    snippet = snippets[name]
    name_entry.delete(0, END)
    name_entry.insert(0, name)
    desc_entry.delete(0, END)
    desc_entry.insert(0, snippet["description"])
    code_text.delete("1.0", END)
    code_text.insert("1.0", snippet["code"])

def delete_snippet():
    selection = listbox.curselection()
    if not selection:
        messagebox.showwarning("Warning", "Select a snippet first.")
        return
    name = listbox.get(selection[0])
    snippets = load_snippets()
    if name in snippets:
        del snippets[name]
        save_snippets(snippets)
        refresh_list()
        messagebox.showinfo("Deleted", f"Snippet '{name}' deleted.")
    else:
        messagebox.showerror("Error", "Snippet not found.")

# --------------------------
# GUI Setup
# --------------------------
def start_gui():
    global listbox, name_entry, desc_entry, code_text
    root = Tk()
    root.title("🧩 Snippet Manager")
    root.geometry("800x500")

    # Left side list
    frame_left = Frame(root)
    frame_left.pack(side=LEFT, fill=Y, padx=10, pady=10)
    Label(frame_left, text="📜 Snippets").pack()
    listbox = Listbox(frame_left, width=30, height=25)
    listbox.pack()
    Button(frame_left, text="🔄 Refresh", command=refresh_list).pack(pady=5)
    Button(frame_left, text="👁 View", command=view_snippet).pack(pady=5)
    Button(frame_left, text="🗑 Delete", command=delete_snippet).pack(pady=5)

    # Right side editor
    frame_right = Frame(root)
    frame_right.pack(side=RIGHT, fill=BOTH, expand=True, padx=10, pady=10)

    Label(frame_right, text="Name:").pack(anchor=W)
    name_entry = Entry(frame_right, width=40)
    name_entry.pack(anchor=W, fill=X)

    Label(frame_right, text="Description:").pack(anchor=W)
    desc_entry = Entry(frame_right, width=40)
    desc_entry.pack(anchor=W, fill=X)

    Label(frame_right, text="Code:").pack(anchor=W)
    code_text = scrolledtext.ScrolledText(frame_right, width=60, height=20)
    code_text.pack(fill=BOTH, expand=True)

    Button(frame_right, text="💾 Save Snippet", command=add_snippet).pack(pady=10)

    refresh_list()
    root.mainloop()

# --------------------------
# Entry Point
# --------------------------
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    start_gui()
