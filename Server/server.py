import socket
import threading
import os
import tkinter as tk
from tkinter import filedialog, messagebox

UPLOAD_FOLDER = ""  # Directory for uploaded files
connected_clients = {}  # Active clients dictionary
file_owner_map = {}  # Mapping files to owners
file_owner_map_lock = threading.RLock()  # Thread-safe access using Reentrant Lock

# Class to handle socket operations with a thread-safe buffer
class SocketBuffer:
    def __init__(self, sock):
        self.sock = sock
        self.lock = threading.Lock()  # Lock for thread-safe operations

    # Send a line of text data (ending with '\n')
    def send_line(self, line):
        with self.lock:
            self.sock.sendall((line + '\n').encode())

    # Send raw data
    def send_data(self, data):
        with self.lock:
            self.sock.sendall(data)

    # Receive a single line of text data
    def recv_line(self):
        buffer = b''
        while True:
            data = self.sock.recv(4096)  # Receive data in chunks
            if not data:
                raise ConnectionError("Client connection lost.")
            buffer += data
            if b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                return line.decode().strip()  # Return the decoded line

# Function to start the server
def start_server():
    global UPLOAD_FOLDER
    port = int(port_entry.get())  # Get server port from input
    UPLOAD_FOLDER = directory_entry.get()  # Get upload directory from input
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)  # Create upload directory if not exists

    load_file_owner_map()  # Load file-owner mapping from disk

    # Handle communication with a connected client
    def handle_client(client_socket, client_address):
        try:
            sock_buf = SocketBuffer(client_socket)
            username = sock_buf.recv_line()  # Receive the username
            if not username:
                client_socket.close()
                return
            if username in connected_clients:
                sock_buf.send_line("ERROR Username already in use.")  # Username conflict
                client_socket.close()
                return

            connected_clients[username] = sock_buf  # Add client to active clients
            log_text.insert(tk.END, f"{username} connected from {client_address}\n")
            update_gui()  # Update GUI

            sock_buf.send_line("OK")  # Send confirmation to client

            while True:
                try:
                    data = sock_buf.recv_line()  # Receive command from client
                    if not data:
                        break

                    if data.startswith("UPLOAD"):
                        # Handle file upload
                        parts = data.split()
                        if len(parts) != 3:
                            sock_buf.send_line("ERROR Invalid UPLOAD command.")
                            continue
                        _, filename, filesize = parts
                        filesize = int(filesize)
                        unique_filename = f"{username}_{filename}"
                        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                        log_text.insert(tk.END, f"Receiving {filename} from {username}...\n")
                        # Save the file
                        try:
                            with open(filepath, "wb") as f:
                                remaining = filesize
                                while remaining > 0:
                                    chunk_size = min(4096, remaining)
                                    data = client_socket.recv(chunk_size)
                                    if not data:
                                        raise ConnectionError("Connection lost.")
                                    f.write(data)
                                    remaining -= len(data)
                        except ConnectionError as e:
                            log_text.insert(tk.END, f"Connection lost while uploading {filename}. Error: {e}\n")
                            if os.path.exists(filepath):  # Remove incomplete file
                                os.remove(filepath)
                            sock_buf.send_line(f"ERROR {filename} could not be uploaded. Connection lost.")
                            continue
                        # Update file-owner map
                        with file_owner_map_lock:
                            file_owner_map[(filename, username)] = unique_filename
                            save_file_owner_map()  # Save to disk
                        log_text.insert(tk.END, f"{filename} uploaded by {username}.\n")
                        sock_buf.send_line(f"{filename} uploaded successfully.")

                    elif data == "LIST":
                        # List all available files
                        with file_owner_map_lock:
                            files_list = [f"{fname} (Owner: {owner})" for (fname, owner), unique_fname in file_owner_map.items()]
                            num_files = len(files_list)
                            sock_buf.send_line(f"RESPONSE:{num_files}")  # Send number of files
                            for file_entry in files_list:
                                sock_buf.send_line(f"RESPONSE:{file_entry}")  # Send file details
                        log_text.insert(tk.END, f"Sent file list to {username}.\n")

                    elif data.startswith("DOWNLOAD"):
                        # Handle file download
                        parts = data.split()
                        if len(parts) != 3:
                            sock_buf.send_line("ERROR Invalid DOWNLOAD command.")
                            continue
                        _, filename, owner = parts
                        key = (filename, owner)
                        with file_owner_map_lock:
                            unique_filename = file_owner_map.get(key)
                        if unique_filename:
                            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                            if os.path.exists(filepath):
                                filesize = os.path.getsize(filepath)
                                sock_buf.send_line(f"RESPONSE:{filesize}")  # Send file size
                                log_text.insert(tk.END, f"Sending '{filename}' ({filesize} bytes) to {username}\n")
                                # Send file data
                                with open(filepath, "rb") as f:
                                    while True:
                                        chunk = f.read(4096)
                                        if not chunk:
                                            break
                                        sock_buf.send_line(f"DATA:{len(chunk)}")  # Data length
                                        sock_buf.send_data(chunk)  # Send data chunk
                                sock_buf.send_line("DATA:0")  # Indicate end of download
                                log_text.insert(tk.END, f"{filename} sent to {username}.\n")
                                if owner in connected_clients and owner != username:
                                    # Notify owner about the download
                                    uploader_sock = connected_clients[owner]
                                    uploader_sock.send_line(f"NOTIFICATION: Your file '{filename}' was downloaded by {username}.")
                            else:
                                sock_buf.send_line("ERROR File not found on server.")
                                log_text.insert(tk.END, f"'{filename}' not found on server for {username}.\n")
                        else:
                            sock_buf.send_line("ERROR File not found.")
                            log_text.insert(tk.END, f"{username} requested a non-existent file {filename}.\n")

                    elif data.startswith("DELETE"):
                        # Handle file deletion
                        parts = data.split()
                        if len(parts) != 2:
                            sock_buf.send_line("ERROR Invalid DELETE command.")
                            continue
                        _, filename = parts
                        key = (filename, username)
                        with file_owner_map_lock:
                            unique_filename = file_owner_map.pop(key, None)  # Remove from map
                            if unique_filename:
                                filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                                if os.path.exists(filepath):
                                    os.remove(filepath)  # Delete the file
                                save_file_owner_map()  # Save changes
                                sock_buf.send_line(f"RESPONSE:{filename} deleted successfully.")
                                log_text.insert(tk.END, f"{username} deleted file {filename}.\n")
                            else:
                                sock_buf.send_line("ERROR You do not own this file or it does not exist.")
                                log_text.insert(tk.END, f"{username} tried to delete a file {filename} that does not exist or is not owned by them.\n")

                    elif data == "EXIT":
                        # Handle client disconnection
                        log_text.insert(tk.END, f"{username} disconnected.\n")
                        break

                    else:
                        # Handle unknown commands
                        sock_buf.send_line("ERROR Unknown command.")
                        log_text.insert(tk.END, f"{username} sent an unknown command: {data}\n")

                except Exception as e:
                    log_text.insert(tk.END, f"Error: {e}\n")
                    break

        finally:
            # Remove client from connected clients list
            connected_clients.pop(username, None)
            client_socket.close()
            log_text.insert(tk.END, f"Connection closed with {username}.\n")
            update_gui()

    # Function to listen for incoming connections
    def server_listener():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', port))  # Bind to all network interfaces
        server.listen(5)
        log_text.insert(tk.END, f"Server listening on port {port}...\n")
        update_gui()
        while True:
            client_socket, client_address = server.accept()  # Accept new connection
            threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True).start()

    threading.Thread(target=server_listener, daemon=True).start()  # Start listener thread

# Save file-owner mapping to disk
def save_file_owner_map():
    with file_owner_map_lock:
        with open('file_owner_map.txt', 'w') as f:
            for (filename, owner), unique_filename in file_owner_map.items():
                f.write(f"{filename}|{owner}|{unique_filename}\n")

# Load file-owner mapping from disk
def load_file_owner_map():
    with file_owner_map_lock:
        file_owner_map.clear()
        if os.path.exists('file_owner_map.txt'):
            with open('file_owner_map.txt', 'r') as f:
                for line in f:
                    if line.strip():
                        filename, owner, unique_filename = line.strip().split('|')
                        file_owner_map[(filename, owner)] = unique_filename

# Update GUI elements
def update_gui():
    # Placeholder for necessary GUI updates
    pass

# Handle application close
def on_closing():
    root.destroy()
    os._exit(0)  # Force exit to close all threads

# GUI setup
root = tk.Tk()
root.title("Server Application")

frame = tk.Frame(root)
frame.pack()

# Server configuration input fields
tk.Label(frame, text="Port:").grid(row=0, column=0)
port_entry = tk.Entry(frame)
port_entry.grid(row=0, column=1)

tk.Label(frame, text="Storage Folder:").grid(row=1, column=0)
directory_entry = tk.Entry(frame)
directory_entry.grid(row=1, column=1)

browse_button = tk.Button(frame, text="Browse", command=lambda: directory_entry.delete(0, tk.END) or directory_entry.insert(0, filedialog.askdirectory()))
browse_button.grid(row=1, column=2)

start_button = tk.Button(frame, text="Start Server", command=start_server)
start_button.grid(row=2, column=1)

# Log display
log_text = tk.Text(root, height=20, width=70)
log_text.pack()

root.protocol("WM_DELETE_WINDOW", on_closing)  # Handle window close
root.mainloop()
