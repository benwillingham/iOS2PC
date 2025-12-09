# iOS2PC
iPhone to PC file transfer app - like airdrop for those without a mac

CS 4390 – Computer Networks  
Final Project – Network Application

This project is a small client–server application that lets you send files from an **iPhone** directly to a **Windows PC** over the internet using a **VPN** and a lightweight **Python Flask** server.

From the user’s point of view:

1. On the iPhone, you take a photo or select a file.
2. Tap **Share → “Send to PC”**.
3. The file appears automatically in a folder on your Windows machine, and a Windows notification pops up (with an image preview for photos).

---

## 1. Architecture Overview

- **Client:** iPhone Shortcut
  - “Send to PC” – sends files via `POST /upload` with a `file` field.

- **Network:**  VPN
  - Both iPhone and PC join the same VPN.

- **Server:** Python Flask app on Windows
  - Listens on `http://<VPN_IP>:8000`.
  - Endpoints:
    - `GET /status` – basic health check.
    - `POST /upload` – receives files and/or URLs.
  - Uses a shared secret header `X-Auth-Token` for application-level auth.

- **Storage & Notifications:**
  - Saves files in a configurable folder (e.g., `C:\Users\<You>\iPhoneDrops`).
  - Converts HEIC/HEIF images to JPEG for Windows compatibility.
  - Shows a Windows notification with filenames and an image preview.

---

## 2. Requirements

### On the PC

- **Python 3** 
- **VPN - I used Tailscale** installed and on same virtual network as phone.
- Optionally, at a batch file that runs the server and place in startup so the reciever is automatically on upon startup.

### On the iPhone
- In addition to being on same VPN as PC, ensure the shortcut is set up to send the attachments to port 8000 of your PCs VPN ip. See attached shortcut template and images for more detail.
