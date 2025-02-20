import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import queue

client_socket = None
client_name = ""
sock_buf = None  # SocketBuffer instance
message_queue = queue.Queue()
data_queue = queue.Queue()

# Class to handle socket operations with thread-safe buffer
class SocketBuffer:
    def __init__(self, sock):
        self.sock = sock
        self.lock = threading.Lock()
        self.buffer = b''

    # Receive one line of data (ending with '\n')
    def recv_line(self):
        while True:
            with self.lock:
                if b'\n' in self.buffer:
                    line, self.buffer = self.buffer.split(b'\n', 1)
                    return line.decode().strip()
            # Receive data from socket
            data = self.sock.recv(4096)
            if not data:
                raise ConnectionError("Connection to server lost.")
            with self.lock:
                self.buffer += data

    # Receive exact number of bytes
    def recv_exact(self, num_bytes):
        with self.lock:
            while len(self.buffer) < num_bytes:
                data = self.sock.recv(4096)
                if not data:
                    raise ConnectionError("Connection to server lost.")
                self.buffer += data
            data, self.buffer = self.buffer[:num_bytes], self.buffer[num_bytes:]
            return data

    # Send a line of data (ending with '\n')
    def send_line(self, line):
        with self.lock:
            self.sock.sendall((line + '\n').encode())

    # Send raw data
    def send_data(self, data):
        with self.lock:
            self.sock.sendall(data)

# Thread to read data from server and process
def reader_thread():
    while True:
        try:
            message = sock_buf.recv_line()  # Receive one line of message
            if message.startswith("NOTIFICATION:"):
                # Display notifications in GUI log
                root.after(0, log_text.insert, tk.END, f"{message}\n")
            elif message.startswith("RESPONSE:"):
                # Put server response into message queue
                message_queue.put(message[len("RESPONSE:"):])
            elif message.startswith("DATA:"):
                # Handle file data reception
                data_length = int(message[len("DATA:"):])
                if data_length == 0:
                    data_queue.put(None)  # Indicate download completion
                else:
                    data = sock_buf.recv_exact(data_length)
                    data_queue.put(data)
            else:
                # Handle unknown messages
                root.after(0, log_text.insert, tk.END, f"{message}\n")
        except Exception as e:
            root.after(0, log_text.insert, tk.END, f"Connection error: {e}\n")
            break

# Function to connect to server
def connect_to_server():
    def connect():
        global client_socket, client_name, sock_buf
        ip = ip_entry.get().strip()  # Get server IP from entry
        port = port_entry.get().strip()  # Get server port from entry
        client_name = username_entry.get().strip()  # Get username from entry

        if not ip or not port or not client_name:
            messagebox.showerror("Error", "IP address, port, and username cannot be empty!")
            return

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip, int(port)))  # Connect to server
            sock_buf = SocketBuffer(client_socket)
            # Send username to server
            sock_buf.send_line(client_name)
            response = sock_buf.recv_line()
            if response.startswith("ERROR"):
                messagebox.showerror("Connection Error", response)
                client_socket.close()
                client_socket = None
            elif response == "OK":
                log_text.insert(tk.END, f"Connected to server {ip}:{port} as {client_name}\n")
                connect_button.config(state=tk.DISABLED)  # Disable connect button
                # Start reader thread
                threading.Thread(target=reader_thread, daemon=True).start()
            else:
                messagebox.showerror("Connection Error", "Received unknown response from server.")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    threading.Thread(target=connect, daemon=True).start()  # Run connection in a separate thread

# Function to upload a file to the server
def upload_file():
    def upload():
        if client_socket is None:
            messagebox.showerror("Error", "Not connected to server!")
            return
        file_path = filedialog.askopenfilename()  # Open file selection dialog
        if file_path:
            filename = os.path.basename(file_path)
            try:
                filesize = os.path.getsize(file_path)
                root.after(0, log_text.insert, tk.END, f"Uploading {filename}...\n")
                # Send upload command with filename and size
                sock_buf.send_line(f"UPLOAD {filename} {filesize}")
                # Send file data in chunks
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        sock_buf.send_data(chunk)
                # Wait for server response
                message = message_queue.get()
                if message.startswith("ERROR"):
                    root.after(0, log_text.insert, tk.END, f"Server error: {message}\n")
                else:
                    root.after(0, log_text.insert, tk.END, f"Server response: {message}\n")
            except Exception as e:
                root.after(0, log_text.insert, tk.END, f"File upload error: {e}\n")
                messagebox.showerror("File Upload Error", str(e))

    threading.Thread(target=upload, daemon=True).start()  # Run upload in a separate thread

# Function to request file list from server
def list_files():
    def list_files_task():
        if client_socket is None:
            messagebox.showerror("Error", "Not connected to server!")
            return
        try:
            sock_buf.send_line("LIST")  # Send list command
            message = message_queue.get()
            if message.startswith("ERROR"):
                root.after(0, log_text.insert, tk.END, f"List Error: {message}\n")
            else:
                num_files = int(message)
                files = []
                for _ in range(num_files):
                    file_entry = message_queue.get()
                    files.append(file_entry)
                response = "\n".join(files)
                root.after(0, log_text.insert, tk.END, f"Available files:\n{response}\n")
        except Exception as e:
            root.after(0, log_text.insert, tk.END, f"List Error: {e}\n")
            messagebox.showerror("List Error", str(e))

    threading.Thread(target=list_files_task, daemon=True).start()  # Run list files in a separate thread

# Function to download a file from server
def download_file():
    def download_task():
        if client_socket is None:
            messagebox.showerror("Error", "Not connected to server!")
            return

        # Open download input window
        download_window = tk.Toplevel(root)
        download_window.title("Download File")

        tk.Label(download_window, text="Filename:").grid(row=0, column=0)
        filename_entry = tk.Entry(download_window)
        filename_entry.grid(row=0, column=1)

        tk.Label(download_window, text="Owner:").grid(row=1, column=0)
        owner_entry = tk.Entry(download_window)
        owner_entry.grid(row=1, column=1)

        def start_download():
            filename = filename_entry.get().strip()
            owner = owner_entry.get().strip()
            download_window.destroy()
            if filename and owner:
                save_path = filedialog.askdirectory()  # Select folder to save file
                if save_path:
                    try:
                        sock_buf.send_line(f"DOWNLOAD {filename} {owner}")  # Send download command
                        message = message_queue.get()
                        if message.startswith("ERROR"):
                            root.after(0, log_text.insert, tk.END, f"Download Error: {message}\n")
                        else:
                            filesize = int(message)
                            root.after(0, log_text.insert, tk.END, f"Downloading {filename} ({filesize} bytes)...\n")
                            received_size = 0
                            with open(os.path.join(save_path, filename), "wb") as f:
                                while True:
                                    data = data_queue.get()
                                    if data is None:
                                        break
                                    f.write(data)
                                    received_size += len(data)
                            root.after(0, log_text.insert, tk.END, f"{filename} downloaded successfully.\n")
                    except Exception as e:
                        root.after(0, log_text.insert, tk.END, f"File Download Error: {e}\n")
                        messagebox.showerror("File Download Error", str(e))
            else:
                messagebox.showerror("Input Error", "Filename and owner cannot be empty.")

        download_button = tk.Button(download_window, text="Download", command=start_download)
        download_button.grid(row=2, column=1)

    threading.Thread(target=download_task, daemon=True).start()

# Function to delete a file from server
def delete_file():
    def delete_task():
        if client_socket is None:
            messagebox.showerror("Error", "Not connected to server!")
            return

        # Open delete input window
        delete_window = tk.Toplevel(root)
        delete_window.title("Delete File")

        tk.Label(delete_window, text="Filename:").grid(row=0, column=0)
        filename_entry = tk.Entry(delete_window)
        filename_entry.grid(row=0, column=1)

        def start_delete():
            filename = filename_entry.get().strip()
            delete_window.destroy()
            if filename:
                try:
                    sock_buf.send_line(f"DELETE {filename}")  # Send delete command
                    message = message_queue.get()
                    if message.startswith("ERROR"):
                        root.after(0, log_text.insert, tk.END, f"Delete Error: {message}\n")
                    else:
                        root.after(0, log_text.insert, tk.END, f"Server response: {message}\n")
                except Exception as e:
                    messagebox.showerror("Delete Error", str(e))
            else:
                messagebox.showerror("Input Error", "Filename cannot be empty.")

        delete_button = tk.Button(delete_window, text="Delete", command=start_delete)
        delete_button.grid(row=1, column=1)

    threading.Thread(target=delete_task, daemon=True).start()

# Handle application close
def on_closing():
    if client_socket:
        try:
            sock_buf.send_line("EXIT")  # Send exit command
            client_socket.close()
        except:
            pass
    root.destroy()

# GUI setup
root = tk.Tk()
root.title("Client Application")

frame = tk.Frame(root)
frame.pack()

# Server connection entries
tk.Label(frame, text="Server IP:").grid(row=0, column=0)
ip_entry = tk.Entry(frame)
ip_entry.grid(row=0, column=1)

tk.Label(frame, text="Port:").grid(row=1, column=0)
port_entry = tk.Entry(frame)
port_entry.grid(row=1, column=1)

tk.Label(frame, text="Username:").grid(row=2, column=0)
username_entry = tk.Entry(frame)
username_entry.grid(row=2, column=1)

# Buttons for actions
connect_button = tk.Button(frame, text="Connect", command=connect_to_server)
connect_button.grid(row=3, column=0)

upload_button = tk.Button(frame, text="Upload File", command=upload_file)
upload_button.grid(row=3, column=1)

list_button = tk.Button(frame, text="List Files", command=list_files)
list_button.grid(row=4, column=0)

download_button = tk.Button(frame, text="Download File", command=download_file)
download_button.grid(row=4, column=1)

delete_button = tk.Button(frame, text="Delete File", command=delete_file)
delete_button.grid(row=5, column=0)

# Log display
log_text = tk.Text(root, height=15, width=60)
log_text.pack()

root.protocol("WM_DELETE_WINDOW", on_closing)  # Handle window close
root.mainloop()
