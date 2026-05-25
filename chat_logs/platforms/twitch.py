import asyncio
import json
import websockets.legacy.client as websockets_client
from datetime import datetime, timezone
from utils import is_platform_active
import urllib.request

PLATFORM = "twitch" 
PLATFORM_LABEL = "[Twitch]"
IRC_URL = "wss://irc-ws.chat.twitch.tv:443"

class TwitchChat:
    def __init__(self, config: dict, broadcast_fn):
        self.oauth     = config["TWITCH_OAUTH"]
        self.username  = config["TWITCH_USERNAME"]
        self.channel   = config["TWITCH_CHANNEL"].lower().lstrip("#")
        self.broadcast = broadcast_fn
        self.seventv   = {}
        self.client_id = config["TWITCH_CLIENT_ID"]
        self.token     = config["TWITCH_OAUTH"].lstrip("oauth:")

    def _escape_html(self, text: str) -> str:
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
    

    def _apply_emotes(self, message: str, emotes_tag: str) -> str:
        placeholders = {}
        if emotes_tag:
            replacements = []
            for emote in emotes_tag.split("/"):
                emote_id, _, positions = emote.partition(":")
                url = f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/dark/1.0"
                for pos in positions.split(","):
                    start, _, end = pos.partition("-")
                    replacements.append((int(start), int(end), url))

            replacements.sort(key=lambda x: x[0], reverse=True)

            for i, (start, end, url) in enumerate(replacements):
                placeholder = f"\x00EMOTE{i}\x00"
                emote_name = message[start:end+1]
                placeholders[placeholder] = f'<img src="{url}" alt="{self._escape_html(emote_name)}" height="20" style="vertical-align:middle">'
                message = message[:start] + placeholder + message[end+1:]

        words = message.split(" ")
        result = []
        for word in words:
            if word in placeholders:
                result.append(placeholders[word])
            elif word in self.seventv:
                url = self.seventv[word]
                result.append(f'<img src="{url}" alt="{self._escape_html(word)}" height="20" style="vertical-align:middle">')
            else:
                result.append(self._escape_html(word))

        return " ".join(result)
    
    def _parse(self, raw:str) -> dict | None:
        if "PRIVMSG" not in raw:
            return None

        try:
            tags = {}
            if raw.startswith("@"):
                tag_str, _, raw = raw[1:].partition(" ")
                for tag in tag_str.split(";"):
                    k, _, v = tag.partition("=")
                    tags[k] = v

            prefix, _, rest = raw.partition(" PRIVMSG ")
            username = prefix.lstrip(":").split("!")[0]
            channel, _, message = rest.partition(" :")
            message = message.strip()

            html = self._apply_emotes(message, tags.get("emotes", ""))

            return {
                "platform":  PLATFORM,
                "label":     PLATFORM_LABEL,
                "username":  username,
                "message":   message.strip(),
                "html":      html,
                "channel":   channel.lstrip("#"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            return None
        
    def _get_twitch_id(self) -> str | None:
        try:
            req = urllib.request.Request(
                f"https://api.twitch.tv/helix/users?login={self.channel}",
                headers={
                    "Client-ID":     self.client_id,
                    "Authorization": f"Bearer {self.token}",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data["data"][0]["id"]
        except Exception as e:
            print(f"[Twitch] Nie można pobrać ID użytkownika: {e}")
            return None

    async def connect(self):
        while not is_platform_active("twitch"):
            await asyncio.sleep(2)

        twitch_id = await asyncio.to_thread(self._get_twitch_id)
        if twitch_id:
            from platforms.seventv import _fetch_7tv_emotes
            self.seventv = await asyncio.to_thread(
                _fetch_7tv_emotes, "twitch", twitch_id
            )

        while is_platform_active("twitch"):
            try:
                async with websockets_client.connect(IRC_URL) as ws:
                    await ws.send(f"PASS {self.oauth}")
                    await ws.send(f"NICK {self.username}")
                    await ws.send(f"CAP REQ :twitch.tv/tags")
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
