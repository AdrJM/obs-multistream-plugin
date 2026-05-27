from flask import Flask
import socket
import os.path
import json
from flask_cors import CORS

# Flask app serving stream status to the OBS dock panel (dock/index.html)
app = Flask(__name__)
CORS(app)  # allow cross-origin requests from the dock (file:// or localhost)
app.config['SERVER_NAME'] = None


@app.route("/status", methods=["GET"])
def status():
    """Return current stream status for all platforms.
    
    Reads status.json written by monitor_streams() in main.py every 2 seconds.
    Returns dict: {platform: {active: bool, bitrate: str}}
    """
    src_status = os.path.join(os.path.dirname(__file__), "config", "status.json")
    with open(src_status, "r") as f:
        return json.load(f)


def is_port_free(port):
    """Check if a port is available before starting the server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0


def run_server():
    """Start Flask server on port 5000 if not already running."""
    if is_port_free(5000):
        app.run(port=5000, use_reloader=False)
    else:
        print("Port 5000 zajęty - serwer już działa")


if __name__ == "__main__":
    app.run(port=5000, use_reloader=False)