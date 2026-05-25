import asyncio
import json
import websockets.legacy.client as websockets_client
import urllib.request
from datetime import datetime, timezone
from utils import is_platform_active
import cloudscraper
import re

PLATFORM = "kick"
PLATFORM_LABEL = "[Kick]"

PUSHER_APP_KEY = "32cbd69e4b950bf97679"
PUSHER_URL = f"wss://ws-us2.pusher.com/app/{PUSHER_APP_KEY}?protocol=7&client=js&version=7.6.0"

def _get_chatroom_id(channel: str) -> int | None:
    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(f"https://kick.com/api/v2/channels/{channel}")
        data = resp.json()
        return data["chatroom"]["id"]
    except Exception as e:
        print(f"[Kick] Nie można pobrać chatroom_id: {e}")
        return None

def _get_kick_user_id(channel: str) -> str | None:
        try:
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(f"https://kick.com/api/v2/channels/{channel}")
            data = resp.json()
            return str(data["user_id"])
        except Exception as e:
            print(f"[Kick] Nie można pobrać user_id: {e}")
            return None
        
class KickChat:
    def __init__(self, config: dict, broadcast_fn):
        self.channel = config["KICK_CHANNEL"].lower()
        self.broadcast = broadcast_fn
        self.seventv   = {}

    def _apply_emotes(self, message: str) -> str:
        placeholders = {}
        counter = [0]

        def replace_kick_emote(match):
            emote_id = match.group(1)
            emote_name = match.group(2)
            url = f"https://files.kick.com/emotes/{emote_id}/fullsize"
            placeholder = f"\x00EMOTE{counter[0]}\x00"
            placeholders[placeholder] = f'<img src="{url}" alt="{emote_name}" height="20" style="vertical-align:middle">'
            counter[0] += 1
            return placeholder

        message = re.sub(r'\[emote:(\d+):([^\]]+)\]', replace_kick_emote, message)

        words = message.split(" ")
        result = []
        for word in words:
            if word in placeholders:
                result.append(placeholders[word])
            elif word in self.seventv:
                url = self.seventv[word]
                result.append(f'<img src="{url}" alt="{word}" height="20" style="vertical-align:middle">')
            else:
                result.append(word)

        return " ".join(result)

    def _parse(self, envelope: dict) -> dict | None:
        try:
            data = json.loads(envelope["data"])
            message = data["content"]
            return {
                "platform":  PLATFORM,
                "label":     PLATFORM_LABEL,
                "username":  data["sender"]["username"],
                "message":   message,
                "html":      self._apply_emotes(message),
                "channel":   self.channel,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            return None
        
    async def connect(self):
        while not is_platform_active("kick"):
            await asyncio.sleep(2)

        while is_platform_active("kick"):
            try:
                chatroom_id = await asyncio.to_thread(_get_chatroom_id, self.channel)
                if not chatroom_id:
                    print("[Kick] Nie można pobrać chatroom_id, przerywam.")
                    return
                
                kick_id = await asyncio.to_thread(_get_kick_user_id, self.channel)
                if kick_id:
                    from platforms.seventv import _fetch_7tv_emotes
                    self.seventv = await asyncio.to_thread(
                        _fetch_7tv_emotes, "kick", kick_id
                    )

                pusher_channel = f"chatrooms.{chatroom_id}.v2"
                print(f"[Kick] chatroom_id={chatroom_id}")

                async with websockets_client.connect(PUSHER_URL) as ws:
                    sub = json.dumps({
                        "event": "pusher:subscribe",
                        "data": {"auth": "", "channel": pusher_channel}
                    })
                    await ws.send(sub)
                    print(f"[Kick] Połączono z #{self.channel}")

                    async for raw in ws:
                        envelope = json.loads(raw)

                        if envelope.get("event") == "pusher:ping":
                            await ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
                            continue
                        if envelope.get("event") != "App\\Events\\ChatMessageEvent":
                            continue
                        
                        msg = self._parse(envelope)
                        if msg:
                            await self.broadcast(msg)
            except Exception as e:
                print(f"[Kick] Błąd: {e}. Ponawianie za 5s...")
                await asyncio.sleep(5)