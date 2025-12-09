import os
import json
import datetime
import textwrap


from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from PIL import Image
from pillow_heif import register_heif_opener

from winotify import Notification as WinNotification

register_heif_opener()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "save_dir": os.path.join(BASE_DIR, "incoming"),
    "auth_token": "password"
}

# If True, delete original .heic/.heif after converting to JPEG
DELETE_HEIC_AFTER_CONVERT = True


def load_config():
    if not os.path.exists(CONFIG_PATH):
        # Write a default config if none exists
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[INFO] No config.json found. Created default at {CONFIG_PATH}. "
              f"Edit it and restart the script.")
        return DEFAULT_CONFIG

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "save_dir" not in cfg or not cfg["save_dir"]:
        cfg["save_dir"] = DEFAULT_CONFIG["save_dir"]
    if "auth_token" not in cfg or not cfg["auth_token"]:
        cfg["auth_token"] = DEFAULT_CONFIG["auth_token"]

    return cfg


config = load_config()
SAVE_DIR = config["save_dir"]
AUTH_TOKEN = config["auth_token"]

os.makedirs(SAVE_DIR, exist_ok=True)

app = Flask(__name__)


def show_notification(title: str, message: str, image_path: str | None = None):
    """
    Show a Windows toast notification with an optional image preview.
    Uses winotify, which accepts PNG/JPG icon paths (must be absolute).
    """
    try:
        icon = ""
        if image_path and os.path.isfile(image_path):
            icon = os.path.abspath(image_path)

        toast = WinNotification(
            app_id="iPhoneDrop",   # any readable name
            title=title,
            msg=message,
            icon=icon              # will show small image on the toast
        )
        toast.show()
    except Exception as e:
        print(f"[WARN] Failed to show toast: {e}")
        print(f"{title}: {message}")



@app.before_request
def check_auth():
    """
    Simple token auth: client must send header:
        X-Auth-Token: <AUTH_TOKEN>

    /status is left open so you can test reachability without the token.
    """
    if request.path == "/status":
        return  # allow /status without auth

    token = request.headers.get("X-Auth-Token")
    if not token or token.strip() != AUTH_TOKEN.strip():
        return jsonify({"error": "unauthorized"}), 401


@app.route("/status", methods=["GET"])
def status():
    """
    Simple health check endpoint.
    """
    return jsonify({"online": True})


def convert_heic_to_jpeg(original_path: str) -> str | None:
    """
    If the file at original_path is HEIC/HEIF, convert it to JPEG and return
    the new JPEG filename (basename only). If conversion fails, return None.
    """
    ext = os.path.splitext(original_path)[1].lower()
    if ext not in (".heic", ".heif"):
        return None

    try:
        img = Image.open(original_path)
        img = img.convert("RGB")  # ensure JPEG-compatible

        base = os.path.splitext(os.path.basename(original_path))[0]
        jpeg_name = base + ".jpg"
        jpeg_path = os.path.join(SAVE_DIR, jpeg_name)

        img.save(jpeg_path, "JPEG", quality=95)
        print(f"[INFO] Converted HEIC to JPEG: {jpeg_path}")

        if DELETE_HEIC_AFTER_CONVERT:
            try:
                os.remove(original_path)
                print(f"[INFO] Deleted original HEIC: {original_path}")
            except OSError as e:
                print(f"[WARN] Could not delete HEIC file {original_path}: {e}")

        return jpeg_name

    except Exception as e:
        print(f"[WARN] Failed to convert HEIC file {original_path}: {e}")
        return None


@app.route("/upload", methods=["POST"])
def upload():
    """
    Accepts multipart/form-data with one or more "file" fields.
    Saves each uploaded file under SAVE_DIR with a timestamp prefix.

    Additionally:
      - If a file is HEIC/HEIF, it is converted to JPEG.
      - A Windows notification is displayed listing received files.
    """
    if "file" not in request.files:
        return jsonify({"error": "no file field in form"}), 400

    files = request.files.getlist("file")
    saved = []
    converted = []

    for f in files:
        if not f.filename:
            continue

        safe_name = secure_filename(f.filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        final_name = f"{timestamp}_{safe_name}"
        full_path = os.path.join(SAVE_DIR, final_name)

        # Save original upload
        f.save(full_path)
        saved.append(final_name)
        print(f"[INFO] Saved file: {full_path}")

        # HEIC/HEIF -> JPEG conversion
        ext = os.path.splitext(safe_name)[1].lower()
        if ext in (".heic", ".heif"):
            jpeg_name = convert_heic_to_jpeg(full_path)
            if jpeg_name:
                converted.append(jpeg_name)

    if not saved:
        return jsonify({"error": "no valid files uploaded"}), 400

    # Build notification message
    display_names = saved.copy()
    if converted:
        display_names.extend([f"(converted) {name}" for name in converted])

    if len(display_names) == 1:
        msg = display_names[0]
    else:
        msg = ", ".join(display_names[:3])
        if len(display_names) > 3:
            msg += ", ..."

    # Choose an image to preview in the toast
    preview_path = None

    # Prefer a converted JPEG if any
    if converted:
        first_jpeg_name = converted[0]
        preview_path = os.path.join(SAVE_DIR, first_jpeg_name)
    else:
        # Otherwise look for any image in saved originals
        for name in saved:
            ext = os.path.splitext(name)[1].lower()
            if ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif"):
                preview_path = os.path.join(SAVE_DIR, name)
                break

    # Show toast with small image preview (if preview_path is not None)
    show_notification("File(s) received from iPhone", msg, image_path=preview_path)

    return jsonify({"saved": saved}), 200


if __name__ == "__main__":
    host = "0.0.0.0"  # listen on all interfaces (including Tailscale)
    port = 8000
    print(f"[INFO] Starting receiver on http://{host}:{port}")
    print(f"[INFO] Saving incoming files to: {SAVE_DIR}")
    app.run(host=host, port=port)
