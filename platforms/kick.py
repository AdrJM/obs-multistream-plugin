import asyncio
import json
import websockets.legacy.client as websockets_client
import urllib.request
from datetime import datetime, timezone
from chat_server import is_platform_active

PLATFORM = "kick"
PLATFORM_LABEL = "[Kick]"

PUSHER_APP_KEY = "32cbd69e4b950bf97679"
PUSHER_URL = f"wss://ws-us2.pusher.com/app/{PUSHER_APP_KEY}?protocol=7&client=js&version=7.6.0"

def _get_chatroom_id(channel: str) -> int | None:
    url = f"https://kick.com/api/v2/channels/{channel}"
    try:
        req = urllib.request.Request(url, headers = {"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout = 10) as resp:
            data = json.loads(resp.read())
            return data["chatroom"]["id"]
    except Exception as e:
        print(f"[Kick] Nie można pobrać chatroom_id: {e}")
        return None
    
class KickChat:
    def __init__(self, config: dict, broadcast_fn):
        self.channel = config["KICK_CHANNEL"].lower()
        self.broadcast = broadcast_fn

    def _parse(self, envelope: dict) -> dict | None:
        try:
            data = json.loads(envelope["data"])
            return {
                "platform":  PLATFORM,
                "label":     PLATFORM_LABEL,
                "username":  data["sender"]["username"],
                "message":   data["content"],
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