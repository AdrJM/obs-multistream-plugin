import asyncio
import os
from websockets.asyncio.server import serve
import json
from datetime import datetime, timezone
import argparse
from dotenv import load_dotenv
from utils import is_platform_active
from platforms.twitch import TwitchChat
from platforms.kick import KickChat
from platforms.youtube import YouTubeChat

# ── Global state ──────────────────────────────────────────────────────────────
connected_clients = set() # Set of active WebSocket connections (OBS overlay clients)
_log_file = None          # Open log file — written to by broadcast() on every incoming message
connectors = {}           #{platform: connector_instance}

async def ws_handler(websocket):
    """Handle a single WebSocket connection from the chat overlay.
    
    Also accepts incoming messages — used for manual testing from browser console.
    Each message is broadcast to all connected clients and saved to the log file.
    """
    connected_clients.add(websocket)
    print(f"Nowy klient ({len(connected_clients)} łącznie)")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") in ("send", "mod"):
                    print(f"[Handler] Odebrano: {data}")
                    if data.get("type") == "send":
                        platform = data.get("platform")
                        message  = data.get("message", "")
                        if platform == "all":
                            for connector in connectors.values():
                                if hasattr(connector, "send_message"):
                                    await connector.send_message(message)
                        elif platform in connectors:
                            await connectors[platform].send_message(message)
                    elif data.get("type") == "mod":
                        platform = data.get("platform")
                        if platform in connectors:
                            connector = connectors[platform]
                            if hasattr(connector, "moderate"):
                                await connector.moderate(
                                    action=data.get("action", ""),
                                    username=data.get("username", ""),
                                    msg_id=data.get("msg_id", ""),
                                    user_id=data.get("user_id", ""),
                                    duration=data.get("duration", 60),
                                )
                else:
                    await broadcast(data)
            except Exception:
                pass
    finally:
        connected_clients.discard(websocket)
        print(f"Klient rozłączony ({len(connected_clients)} łącznie)")


async def broadcast(message: dict):
    print(f"[broadcast] wysyłam: {message.get('username')} - {message.get('message', '')[:30]}")
    """Save message to log file and send to all connected overlay clients.
    
    Called by platform connectors (Twitch, Kick, YouTube) on every chat message.
    Uses asyncio.gather to send to all clients in parallel.
    return_exceptions=True prevents one broken client from stopping the rest.
    """
    if _log_file:
        _log_file.write(json.dumps(message, ensure_ascii=False) + "\n")
        _log_file.flush()  # flush immediately so logs aren't lost on crash

    if connected_clients:
        data = json.dumps(message, ensure_ascii=False)
        await asyncio.gather(
            *[ws.send(data) for ws in connected_clients],
            return_exceptions=True
        )


async def main():
    global _log_file

    # Accept --logs-path argument from main.py (OBS script)
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-path", default="logs")
    args = parser.parse_args()

    # Load credentials — chat.env overrides keys.env for shared variables
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", "keys.env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", "chat.env"))

    # Config dict passed to each platform connector
    config = {
        "TWITCH_OAUTH":       os.getenv("TWITCH_OAUTH"),
        "TWITCH_USERNAME":    os.getenv("TWITCH_USERNAME"),
        "TWITCH_CHANNEL":     os.getenv("TWITCH_CHANNEL"),
        "TWITCH_CLIENT_ID":   os.getenv("TWITCH_CLIENT_ID"),
        "KICK_CHANNEL":       os.getenv("KICK_CHANNEL"),
        "YOUTUBE_API_KEY":    os.getenv("YOUTUBE_API_KEY"),
        "YOUTUBE_CHANNEL_ID": os.getenv("YOUTUBE_CHANNEL_ID"),
    }

    # Create log file named with stream start timestamp
    os.makedirs(args.logs_path, exist_ok=True)
    stream_start = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(args.logs_path, f"{stream_start}_stream.jsonl")
    _log_file = open(log_path, "w", encoding="utf-8")
    print(f"Plik logu: {log_path}")

    # Start WebSocket server and all platform connectors concurrently
    async with serve(ws_handler, "localhost", 5001):
        print("WebSocket gotowy na ws://localhost:5001")
        twitch = TwitchChat(config, broadcast)
        kick   = KickChat(config, broadcast)
        youtube = YouTubeChat(config, broadcast)

        connectors["twitch"]  = twitch
        connectors["kick"]    = kick
        connectors["youtube"] = youtube

        await asyncio.gather(
            twitch.connect(),
            kick.connect(),
            youtube.connect(),
        )


if __name__ == "__main__":
    asyncio.run(main())