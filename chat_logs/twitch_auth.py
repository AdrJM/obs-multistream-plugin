from flask import Flask, request, redirect
import urllib.request
import urllib.parse
import json
import os
import webbrowser
import threading
from dotenv import load_dotenv

app = Flask(__name__)

BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
CHAT_ENV   = os.path.join(BASE_DIR, "config", "chat.env")
REDIRECT   = "http://localhost:5002/callback"
SCOPES = "chat:read chat:edit moderator:manage:chat_messages moderator:manage:banned_users channel:moderate"

load_dotenv(CHAT_ENV)
CLIENT_ID     = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")


@app.route("/")
def index():
    """Redirect user to Twitch OAuth authorization page."""
    params = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT,
        "response_type": "code",
        "scope":         SCOPES,
    })
    return redirect(f"https://id.twitch.tv/oauth2/authorize?{params}")


@app.route("/callback")
def callback():
    """Receive authorization code from Twitch and exchange for access token."""
    code = request.args.get("code")
    if not code:
        return "Błąd autoryzacji — brak kodu.", 400

    # Exchange code for access_token + refresh_token
    data = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT,
    }).encode()

    req = urllib.request.Request(
        "https://id.twitch.tv/oauth2/token",
        data=data,
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    access_token  = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Save tokens to chat.env
    _save_tokens(access_token, refresh_token)

    # Fetch and save username automatically
    user = _fetch_twitch_user(access_token, CLIENT_ID)
    if user:
        _save_user(user["login"])
        msg = f"<h2>✓ Zalogowano jako {user['display_name']}! Możesz zamknąć tę kartę.</h2>"
    else:
        msg = "<h2>✓ Zalogowano pomyślnie! Możesz zamknąć tę kartę.</h2>"

    # Shut down server
    threading.Thread(target=_shutdown).start()
    return msg

def _save_tokens(access_token: str, refresh_token: str):
    """Update TWITCH_OAUTH and TWITCH_REFRESH_TOKEN in chat.env."""
    existing = {}
    if os.path.exists(CHAT_ENV):
        with open(CHAT_ENV, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

    existing["TWITCH_OAUTH"]         = f"oauth:{access_token}"
    existing["TWITCH_REFRESH_TOKEN"] = refresh_token

    with open(CHAT_ENV, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    print(f"[TwitchAuth] Token zapisany do chat.env")

def _fetch_twitch_user(access_token: str, client_id: str) -> dict | None:
    """Fetch Twitch username from Helix API using the fresh access token."""
    try:
        req = urllib.request.Request(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Client-Id":     client_id,
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data["data"][0]
    except Exception as e:
        print(f"[TwitchAuth] Nie można pobrać danych użytkownika: {e}")
        return None

def _save_user(username: str):
    """Save TWITCH_USERNAME and TWITCH_CHANNEL to chat.env."""
    existing = {}
    if os.path.exists(CHAT_ENV):
        with open(CHAT_ENV, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

    existing["TWITCH_USERNAME"] = username
    existing["TWITCH_CHANNEL"]  = username  # same as username by default

    with open(CHAT_ENV, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    print(f"[TwitchAuth] Username zapisany: {username}")


def _shutdown():
    import time
    time.sleep(1)
    os._exit(0)


if __name__ == "__main__":
    # Open browser automatically and start Flask
    threading.Timer(1, lambda: webbrowser.open("http://localhost:5002")).start()
    app.run(port=5002, use_reloader=False)