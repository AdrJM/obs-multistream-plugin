import urllib.request
import json

SEVENTV_API = "https://7tv.io/v3"

def _fetch_7tv_emotes(platform: str, channel_id: str) -> dict:
    """
    Zwraca słownik {nazwa_emotki: url} dla danego kanału.
    platform: "twitch" lub "kick"
    channel_id: ID kanału na danej platformie
    """
    emotes = {}

    # Globalne emotki 7TV
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

    # Kanałowe emotki 7TV
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