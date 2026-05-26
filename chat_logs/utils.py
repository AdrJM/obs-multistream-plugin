import json
import os

# Path to status.json — written by main.py, read by platform connectors
STATUS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "status.json")

def is_platform_active(platform: str) -> bool:
    """Check if a given platform is currently streaming.
    
    Reads status.json which is updated every 2s by monitor_streams() in main.py.
    Returns False if the file doesn't exist or can't be read.
    """
    try:
        with open(STATUS_PATH, "r") as f:
            status = json.load(f)
        return status.get(platform, {}).get("active", False)
    except Exception:
        return False