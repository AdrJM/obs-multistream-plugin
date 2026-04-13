from flask import Flask
import socket
import os.path
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['SERVER_NAME'] = None

@app.route("/status", methods=["GET"])
def status():
    all_status = {}
    src_status = os.path.join(os.path.dirname(__file__), "config", "status.json")
    with open(src_status, "r") as f:
        all_status = json.load(f)
    return all_status


def is_port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

def run_server():
    if is_port_free(5000):
        app.run(port=5000, use_reloader=False)
    else:
        print("Port 5000 zajęty - serwer już działa")

if __name__ == "__main__":
    app.run(port=5000, use_reloader=False)
