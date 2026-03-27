import os
import base64
import subprocess
import threading
import time
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
from datetime import datetime
import config
from models import init_db, log_violation, get_category_stats, get_total_count
from ai_detector import detect_category

app = Flask(__name__, static_folder="static")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize database
init_db()

# Create screenshots directory
if not os.path.exists(os.path.join("static", "screenshots")):
    os.makedirs(os.path.join("static", "screenshots"))

# Store device heartbeat timestamps, violation counts, and student names
devices_last_seen = {}
device_violations = {}
device_names = {}
monitoring_active_devices = set() 
connected_devices_count = 0

def network_scanner():
    global connected_devices_count
    while True:
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True)
            output = result.stdout
            lines = [line for line in output.split('\n') if '(' in line and ')' in line]
            new_count = len(lines)
            
            if new_count != connected_devices_count:
                connected_devices_count = new_count
                socketio.emit("network_update", {
                    "devices": connected_devices_count
                })
        except Exception as e:
            pass # arp scan error
        time.sleep(15)

# Start background network scanner
scanner_thread = threading.Thread(target=network_scanner, daemon=True)
scanner_thread.start()

disconnected_notified_devices = set()

def disconnection_checker():
    while True:
        now = datetime.utcnow()
        for device, last_seen in list(devices_last_seen.items()):
            # If no heartbeat for > 20 seconds, it's a high threat (Extension might be disabled)
            if (now - last_seen).total_seconds() > 20:
                if device not in disconnected_notified_devices:
                    disconnected_notified_devices.add(device)
                    student_name = device_names.get(device, "Unknown Student")
                    
                    # Emit a special critical alert
                    socketio.emit("new_alert", {
                        "device": device,
                        "name": student_name,
                        "url": "N/A - EXTENSION DISABLED",
                        "time": datetime.utcnow().isoformat(),
                        "category": "CRITICAL",
                        "reason": "🚨 EXTENSION TAMPERING: CONNECTION LOST",
                        "screenshot": None,
                        "is_critical": True # Flag for UI highlighting
                    })
                    
                    socketio.emit("device_status", {
                        "device": device,
                        "name": student_name,
                        "status": "tampered",
                        "violations": device_violations.get(device, 0)
                    })
            else:
                # Device is back online
                if device in disconnected_notified_devices:
                    disconnected_notified_devices.remove(device)
                    
        time.sleep(5)

# Start disconnection checker
checker_thread = threading.Thread(target=disconnection_checker, daemon=True)
checker_thread.start()

# Expanded Dynamic blacklist
blacklist = [
    "youtube.com",
    "instagram.com",
    "facebook.com",
    "netflix.com",
    "twitter.com",
    "primevideo.com",
    "disneyplus.com",
    "chatgpt.com",
    "openai.com",
    "perplexity.ai",
    "claude.ai",
    "github.com/copilot",
    "reddit.com",
    "twitch.tv",
    "discord.com"
]

# ======================
# ROUTES
# ======================

@app.route("/")
def dashboard():
    total = get_total_count()
    return render_template("dashboard.html", total=total)

@app.route("/analytics")
def analytics():
    data = get_category_stats()
    return render_template("analytics.html", data=data)

@app.route("/alert", methods=["POST"])
def receive_alert():
    data = request.json

    if data.get("api_key") != config.API_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    device = data["device"]
    url = data["url"]
    time_str = data["time"]
    reason = data.get("reason", "Unknown")
    screenshot_b64 = data.get("screenshot")
    student_name = data.get("student_name", "Unknown")

    category = detect_category(url)
    log_violation(device, url, category, time_str)
    
    device_violations[device] = device_violations.get(device, 0) + 1
    device_names[device] = student_name 

    screenshot_path = None
    if screenshot_b64:
        try:
            filename = f"{device}_{int(time.time())}.png"
            filepath = os.path.join("static", "screenshots", filename)
            if "base64," in screenshot_b64:
                screenshot_b64 = screenshot_b64.split("base64,")[1]
            image_data = base64.b64decode(screenshot_b64)
            with open(filepath, "wb") as f:
                f.write(image_data)
            screenshot_path = f"/static/screenshots/{filename}"
        except Exception as e:
            print("Error saving screenshot:", e)

    socketio.emit("new_alert", {
        "device": device,
        "name": student_name,
        "url": url,
        "time": time_str,
        "category": category,
        "reason": reason,
        "screenshot": screenshot_path,
        "device_violations": device_violations[device]
    })

    socketio.emit("device_status", {
        "device": device,
        "name": student_name,
        "status": "violation",
        "violations": device_violations[device]
    })

    return jsonify({"status": "logged"}), 200

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.json
    device = data.get("device")
    student_name = data.get("student_name", "Unknown")

    devices_last_seen[device] = datetime.utcnow()
    device_names[device] = student_name
    
    monitoring_status = "ON" if device in monitoring_active_devices else "OFF"
    
    socketio.emit("device_heartbeat", {
        "device": device,
        "name": student_name,
        "status": "normal",
        "violations": device_violations.get(device, 0)
    })

    return jsonify({
        "status": "alive", 
        "monitoring": monitoring_status
    })

@app.route("/toggle_monitoring", methods=["POST"])
def toggle_monitoring():
    data = request.json
    device = data.get("device")
    action = data.get("action") # "START" or "STOP"
    
    if action == "START":
        monitoring_active_devices.add(device)
    else:
        monitoring_active_devices.discard(device)
        
    return jsonify({"status": "updated"})

@app.route("/live_monitoring", methods=["POST"])
def live_monitoring():
    data = request.json
    device = data.get("device")
    screenshot = data.get("screenshot")
    
    if device in monitoring_active_devices:
        socketio.emit("live_stream", {
            "device": device,
            "screenshot": screenshot
        })
        
    return jsonify({"status": "received"})

@app.route("/get_blacklist")
def get_blacklist():
    return jsonify(blacklist)

# Serve static files correctly
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# ======================
# RUN
# ======================

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050)