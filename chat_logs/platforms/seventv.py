import urllib.request
import json

SEVENTV_API = "https://7tv.io/v3"


def _fetch_7tv_emotes(platform: str, channel_id: str) -> dict:
    """Fetch 7TV emotes for a given channel and return as {name: url} dict.

    Loads two sets:
    - Global emotes: available on all channels
    - Channel emotes: set by the streamer for their specific channel

    Channel emotes override global ones if names conflict.

    Args:
        platform: "twitch" or "kick"
        channel_id: numeric user ID on the given platform
    """
    emotes = {}

    # Global emotes — same for everyone, loaded first
    try:
        req = urllib.request.Request(
            f"{SEVENTV_API}/emote-sets/global",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            for emote in data.get("emotes", []):
                name = emote["name"]
                emote_id = emote["id"]
                emotes[name] = f"https://cdn.7tv.app/emote/{emote_id}/1x.webp"
    except Exception as e:
        print(f"[7TV] Błąd pobierania globalnych emotek: {e}")

    # Channel emotes — specific to this streamer, may override global names
    try:
        req = urllib.request.Request(
            f"{SEVENTV_API}/users/{platform}/{channel_id}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            for emote in data.get("emote_set", {}).get("emotes", []):
                name = emote["name"]
                emote_id = emote["id"]
                emotes[name] = f"https://cdn.7tv.app/emote/{emote_id}/1x.webp"
    except Exception as e:
        print(f"[7TV] Błąd pobierania emotek kanału: {e}")

    print(f"[7TV] Załadowano {len(emotes)} emotek dla {platform}/{channel_id}")
    return emotes