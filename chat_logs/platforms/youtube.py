import asyncio
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from utils import is_platform_active

PLATFORM = "youtube"
PLATFORM_LABEL = "[YouTube]"
API_BASE = "https://www.googleapis.com/youtube/v3"


def _yt_get(endpoint: str, params: dict) -> dict:
    """Send a GET request to YouTube Data API v3 and return parsed JSON.
    
    No error handling here — callers are responsible for try/except.
    """
    url = f"{API_BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _get_live_chat_id(api_key: str, channel_id: str) -> str | None:
    """Fetch liveChatId for the currently active broadcast on the given channel.
    
    Returns None if no active broadcast is found or on any API error.
    """
    try:
        data = _yt_get("liveBroadcasts", {
            "part":            "snippet",
            "broadcastStatus": "active",
            "channelId":       channel_id,
            "key":             api_key,
        })
        items = data.get("items", [])
        if not items:
            return None
        return items[0]["snippet"]["liveChatId"]
    except Exception as e:
        print(f"[YouTube] Nie można pobrać liveChatId: {e}")
        return None


class YouTubeChat:
    def __init__(self, config: dict, broadcast_fn):
        self.api_key    = config["YOUTUBE_API_KEY"]
        self.channel_id = config["YOUTUBE_CHANNEL_ID"]
        self.broadcast  = broadcast_fn

    def _parse(self, item: dict) -> dict | None:
        """Parse a single YouTube Live Chat message into unified format.
        
        Skips non-text events (superchats, membership alerts, etc.).
        """
        try:
            snippet = item["snippet"]
            if snippet.get("type") != "textMessageEvent":
                return None
            return {
                "platform":  PLATFORM,
                "label":     PLATFORM_LABEL,
                "username":  item["authorDetails"]["displayName"],
                "message":   snippet["textMessageDetails"]["messageText"],
                "channel":   self.channel_id,
                "timestamp": snippet["publishedAt"],
            }
        except Exception:
            return None

    async def _poll(self, live_chat_id: str):
        """Poll YouTube Live Chat API for new messages.
        
        Uses pageToken to avoid re-fetching already seen messages.
        Respects pollingIntervalMillis returned by the API to avoid rate limiting.
        Returns when stream goes offline or on unrecoverable error.
        """
        page_token = None
        interval = 5

        while is_platform_active("youtube"):
            try:
                params = {
                    "part":       "snippet,authorDetails",  # no space after comma
                    "liveChatId": live_chat_id,
                    "key":        self.api_key,
                    "maxResults": 200,
                }
                if page_token:
                    params["pageToken"] = page_token

                data = await asyncio.to_thread(_yt_get, "liveChat/messages", params)

                for item in data.get("items", []):
                    msg = self._parse(item)
                    if msg:
                        await self.broadcast(msg)

                # Update token and use API-suggested polling interval
                page_token = data.get("nextPageToken")
                interval   = data.get("pollingIntervalMillis", 5000) / 1000
                await asyncio.sleep(interval)

            except Exception as e:
                print(f"[YouTube] Błąd pollingu: {e}. Ponawianie za 10s...")
                await asyncio.sleep(10)
                return  # return to connect() to re-fetch liveChatId

    async def connect(self):
        """Wait for YouTube to go live, then start polling chat messages."""
        while not is_platform_active("youtube"):
            await asyncio.sleep(2)

        while is_platform_active("youtube"):
            live_chat_id = await asyncio.to_thread(
                _get_live_chat_id, self.api_key, self.channel_id
            )
            if not live_chat_id:
                print("[YouTube] Brak aktywnego streama, sprawdzam za 10s...")
                await asyncio.sleep(10)
                continue

            print(f"[YouTube] Połączono, liveChatId: {live_chat_id}")
            await self._poll(live_chat_id)