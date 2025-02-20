# Cloud File Storage and Publishing System

## Project Overview
This project is a **client-server application** implemented using **TCP sockets**. The application acts as a **cloud file storage and publishing system**, where users can:
- **Upload** text files to a central server
- **Download** files uploaded by other users
- **View the list** of uploaded files and their respective owners
- **Delete** their own uploaded files

## Features
### Server
- Accepts multiple client connections simultaneously.
- Stores uploaded files in a predefined folder.
- Maintains a list of files and their owners.
- Allows clients to upload, download, and delete their own files.
- Ensures that filenames are unique per user by appending the uploader's name.
- Displays all activity logs in the GUI.
- Handles errors gracefully (e.g., duplicate usernames, file access issues).

### Client
- Connects to the server via a **GUI** where the user enters the **server IP, port, and username**.
- Allows users to browse and **upload** text files.
- Requests and displays the **list of available files** on the server.
- Enables users to **download** files uploaded by others.
- Users can **delete** their own uploaded files.
- Displays all operations and notifications in a GUI log box.

## Technologies Used
- **Python** (Recommended language as per project specifications)
- **Tkinter** (for GUI development)
- **Socket Programming** (for TCP-based client-server communication)
- **Threading** (for handling multiple connections and file transfers)

## Installation & Usage
### Server Setup
1. Run the **server script**:
   ```sh
   python server.py
   ```
2. Enter the **port number** and **select the folder** where uploaded files will be stored.
3. Click the **Start Server** button.

### Client Setup
1. Run the **client script**:
   ```sh
   python client.py
   ```
2. Enter the **server IP address**, **port number**, and **a unique username**.
3. Click **Connect** to establish a connection with the server.
4. Use the buttons to:
   - **Upload** a file
   - **View** the list of available files
   - **Download** a file
   - **Delete** a file

## File Structure
```
Project Folder
│── server.py          # Server-side script
│── client.py          # Client-side script
│── README.md          # Project documentation
│── file_owner_map.txt # Stores file-ownership mappings (auto-generated)
```

## Notes
- The server **must be running** before clients can connect.
- Clients must use **unique usernames**.
- Only **text files (ASCII characters)** are supported.
- Large files are transferred in **chunks** to handle big data efficiently.

## Future Enhancements
- Support for binary file types (e.g., PDFs, images).
- Implement user authentication (login & password-based access).
- Improve file access control (private vs. public files).

## Authors
- **Toprak Aktepe** (GitHub: [toprakak07](https://github.com/toprakak07))

