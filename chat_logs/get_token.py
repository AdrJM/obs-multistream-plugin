import urllib.request
import urllib.parse
import json
import os
from dotenv import load_dotenv

# Load client credentials from chat.env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", "chat.env"))

client_id     = os.getenv("TWITCH_CLIENT_ID")
client_secret = os.getenv("TWITCH_CLIENT_SECRET")

print("Client ID:", client_id)
print("Client Secret:", client_secret)

# Build POST body for client_credentials OAuth flow.
# NOTE: This generates an app-level token — valid for Helix API but NOT for IRC chat.
# For IRC you need a User Access Token from twitchtokengenerator.com (chat:read scope).
data = urllib.parse.urlencode({
    "client_id":     client_id,
    "client_secret": client_secret,
    "grant_type":    "client_credentials"
}).encode()

req = urllib.request.Request(
    "https://id.twitch.tv/oauth2/token",
    data=data,
    method="POST"
)

with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read())
    print("Token:", result["access_token"])