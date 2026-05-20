import asyncio
import websockets.legacy.client as websockets_client
from datetime import datetime, timezone
from utils import is_platform_active

PLATFORM = "twitch" 
PLATFORM_LABEL = "[Twitch]"
IRC_URL = "wss://irc-ws.chat.twitch.tv:443"

class TwitchChat:
    def __init__(self, config: dict, broadcast_fn):
        self.oauth     = config["TWITCH_OAUTH"]
        self.username  = config["TWITCH_USERNAME"]
        self.channel   = config["TWITCH_CHANNEL"].lower().lstrip("#")
        self.broadcast = broadcast_fn

    def _parse(self, raw:str) -> dict | None:
        if "PRIVMSG" not in raw:
            return None
        try:
            prefix, _, rest = raw.partition(" PRIVMSG ")
            username = prefix.lstrip(":").split("!")[0]
            channel, _, message = rest.partition(" :")
            return {
                "platform": PLATFORM,
                "label": PLATFORM_LABEL,
                "username": username,
                "message": message.strip(),
                "channel": channel.lstrip("#"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            return None

    async def connect(self):
        while not is_platform_active("twitch"):
            await asyncio.sleep(2)

        while is_platform_active("twitch"):
            try:
                async with websockets_client.connect(IRC_URL) as ws:
                    await ws.send(f"PASS {self.oauth}")
                    await ws.send(f"NICK {self.username}")
                    await ws.send(f"JOIN #{self.channel}")
                    print(f"[Twitch] Połączono z #{self.channel}")

                    async for raw in ws:
                        message = str(raw)
                        if message.startswith("PING"):
                            await ws.send("PONG :tmi.twitch.tv")
                            continue

                        msg = self._parse(message)
                        if msg:
                            await self.broadcast(msg)

            except Exception as e:
                print(f"[Twitch] Błąd: {e}. Ponawianie za 5s...")
                await asyncio.sleep(5)
