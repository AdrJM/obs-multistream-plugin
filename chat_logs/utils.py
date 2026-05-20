import json
import os

STATUS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "status.json")

def is_platform_active(platform: str) -> bool:
    try:
        with open(STATUS_PATH, "r") as f:
            status = json.load(f)
        return status.get(platform, {}).get("active", False)
    except Exception:
        return False