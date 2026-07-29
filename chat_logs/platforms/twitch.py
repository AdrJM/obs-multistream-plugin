import asyncio
import json
from websockets.asyncio.client import connect as ws_connect
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
        self.seventv   = {}  # 7TV emote dict: {name: url}
        self.client_id = config["TWITCH_CLIENT_ID"]
        self.token     = config["TWITCH_OAUTH"].lstrip("oauth:")  # bare token for Helix API
        self._ws = None # active IRC WebSocket connection

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters to prevent XSS in overlay innerHTML."""
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _apply_emotes(self, message: str, emotes_tag: str) -> str:
        """Replace Twitch emote codes and 7TV emote names with <img> tags.
        
        Twitch emotes come from IRC tags as "id:start-end,start-end/id:start-end".
        We replace them using placeholders first (null byte delimited) to avoid
        index shifting when substituting from right to left.
        7TV emotes are matched word-by-word against the loaded emote dict.
        All plain text is HTML-escaped to prevent XSS.
        """
        placeholders = {}

        if emotes_tag:
            replacements = []
            for emote in emotes_tag.split("/"):
                emote_id, _, positions = emote.partition(":")
                url = f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/dark/1.0"
                for pos in positions.split(","):
                    start, _, end = pos.partition("-")
                    replacements.append((int(start), int(end), url))

            # Sort in reverse order so substitutions don't shift remaining indices
            replacements.sort(key=lambda x: x[0], reverse=True)

            for i, (start, end, url) in enumerate(replacements):
                placeholder = f"\x00EMOTE{i}\x00"
                emote_name = message[start:end+1]
                placeholders[placeholder] = f'<img src="{url}" alt="{self._escape_html(emote_name)}" height="20" style="vertical-align:middle">'
                message = message[:start] + placeholder + message[end+1:]

        # Process word by word — check placeholders then 7TV then plain text
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

    def _parse(self, raw: str) -> dict | None:
        """Parse a raw IRC message into unified chat message format.
        
        Handles tagged messages (starting with @) which contain emote metadata.
        Only processes PRIVMSG — ignores JOIN, PING, USERSTATE, etc.
        """
        if "PRIVMSG" not in raw:
            return None
        try:
            tags = {}
            if raw.startswith("@"):
                tag_str, _, raw = raw[1:].partition(" ")
                for tag in tag_str.split(";"):
                    k, _, v = tag.partition("=")
                    tags[k] = v

            print(f"[Twitch] tags id={tags.get('id')} user-id={tags.get('user-id')}")         

            prefix, _, rest = raw.partition(" PRIVMSG ")
            username = prefix.lstrip(":").split("!")[0]
            channel, _, message = rest.partition(" :")
            message = message.strip()

            html = self._apply_emotes(message, tags.get("emotes", ""))
            return {
                "platform":  PLATFORM,
                "label":     PLATFORM_LABEL,
                "username":  username,
                "message":   message,
                "html":      html,
                "channel":   channel.lstrip("#"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "id":        tags.get("id", ""),       
                "user_id":   tags.get("user-id", ""), 
            }
        except Exception:
            return None

    def _get_twitch_id(self) -> str | None:
        """Fetch Twitch user ID via Helix API — needed to load 7TV channel emotes.
        
        Requires a valid User Access Token (not client_credentials token).
        """
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
        """Wait for Twitch to go live, load 7TV emotes, then connect to IRC chat."""
        while not is_platform_active("twitch"):
            await asyncio.sleep(2)

        # Load 7TV emotes — requires Twitch user ID from Helix API
        twitch_id = await asyncio.to_thread(self._get_twitch_id)
        if twitch_id:
            from platforms.seventv import _fetch_7tv_emotes
            self.seventv = await asyncio.to_thread(
                _fetch_7tv_emotes, "twitch", twitch_id
            )

        while is_platform_active("twitch"):
            try:
                async with ws_connect(IRC_URL) as ws:
                    self._ws = ws 
                    await ws.send(f"PASS {self.oauth}")
                    await ws.send(f"NICK {self.username}")
                    await ws.send(f"CAP REQ :twitch.tv/tags")  # request emote metadata
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

                    self._ws = None

            except Exception as e:
                self._ws = None
                print(f"[Twitch] Błąd: {e}. Ponawianie za 5s...")
                await asyncio.sleep(5)

    async def send_message(self, message: str):
        """Send a message to Twitch chat via IRC."""
        print(f"[Twitch] send_message wywołane, _ws={self._ws is not None}, msg={message}")
        if self._ws:
            await self._ws.send(f"PRIVMSG #{self.channel} :{message}")
            
            # Broadcast manually since Twitch doesn't echo own messages back
            await self.broadcast({
                "platform":  PLATFORM,
                "label":     PLATFORM_LABEL,
                "username":  self.username,
                "message":   message,
                "html":      self._escape_html(message),
                "channel":   self.channel,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def _api_delete(self, url: str, headers: dict):
        req = urllib.request.Request(url, headers=headers, method="DELETE")
        try:
            urllib.request.urlopen(req, timeout=10)
            print(f"[Twitch] DELETE {url} OK")
        except Exception as e:
            print(f"[Twitch] DELETE błąd: {e}")

    def _api_post(self, url: str, headers: dict, body: bytes):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            urllib.request.urlopen(req, timeout=10)
            print(f"[Twitch] POST {url} OK")
        except Exception as e:
            print(f"[Twitch] POST błąd: {e}")        

    async def moderate(self, action: str, username: str, msg_id: str = "", user_id: str = "", duration: int = 0):
        """Perform moderation action via Twitch Helix API."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Client-Id":     self.client_id,
            "Content-Type":  "application/json",
        }
        
        # Get broadcaster ID (needed for all mod endpoints)
        broadcaster_id = await asyncio.to_thread(self._get_twitch_id)
        if not broadcaster_id:
            print("[Twitch] Nie można wykonać moderacji — brak broadcaster_id")
            return

        match action:
            case "delete":
                # Delete specific message
                url = f"https://api.twitch.tv/helix/moderation/chat?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}&message_id={msg_id}"
                await asyncio.to_thread(self._api_delete, url, headers)

            case "timeout":
                # Timeout user
                url = f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}"
                body = json.dumps({"data": {"user_id": user_id, "duration": duration, "reason": ""}}).encode()
                await asyncio.to_thread(self._api_post, url, headers, body)

            case "ban":
                # Permanent ban
                url = f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}"
                body = json.dumps({"data": {"user_id": user_id, "reason": ""}}).encode()
                await asyncio.to_thread(self._api_post, url, headers, body)

            case _:
                print(f"[Twitch] Nieznana akcja moderacji: {action}")