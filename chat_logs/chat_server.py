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

# Set of active WebSocket connections (OBS overlay clients)
connected_clients = set()

# Open log file — written to by broadcast() on every incoming message
_log_file = None


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
                await broadcast(data)
            except Exception:
                pass
    finally:
        connected_clients.discard(websocket)
        print(f"Klient rozłączony ({len(connected_clients)} łącznie)")


async def broadcast(message: dict):
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
        await asyncio.gather(
            TwitchChat(config, broadcast).connect(),
            KickChat(config, broadcast).connect(),
            YouTubeChat(config, broadcast).connect(),
        )


if __name__ == "__main__":
    asyncio.run(main())