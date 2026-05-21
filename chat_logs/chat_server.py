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

connected_clients = set()
_log_file = None
STATUS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "status.json")

async def ws_handler(websocket):
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
    if _log_file:
        _log_file.write(json.dumps(message, ensure_ascii=False) + "\n")
        _log_file.flush()

    if connected_clients:
        data = json.dumps(message, ensure_ascii=False)
        await asyncio.gather(
            *[ws.send(data) for ws in connected_clients],
            return_exceptions = True
        )

async def main():
    global _log_file

    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-path", default="logs")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", "keys.env"))

    config = {
        "TWITCH_OAUTH":       os.getenv("TWITCH_OAUTH"),
        "TWITCH_USERNAME":    os.getenv("TWITCH_USERNAME"),
        "TWITCH_CHANNEL":     os.getenv("TWITCH_CHANNEL"),
        "KICK_CHANNEL":       os.getenv("KICK_CHANNEL"),
        "YOUTUBE_API_KEY":    os.getenv("YOUTUBE_API_KEY"),
        "YOUTUBE_CHANNEL_ID": os.getenv("YOUTUBE_CHANNEL_ID"),
    }

    os.makedirs(args.logs_path, exist_ok = True)
    stream_start = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(args.logs_path, f"{stream_start}_stream.jsonl")
    _log_file = open(log_path, "w", encoding = "utf-8")
    print(f"Plik logu: {log_path}")

    async with serve(ws_handler, "localhost", 5001):
        print("WebSocket gotowy na ws://localhost:5001")
        await asyncio.gather(
            TwitchChat(config, broadcast).connect(),
            KickChat(config, broadcast).connect(),
            YouTubeChat(config, broadcast).connect(),
        )

if __name__ == "__main__":
    asyncio.run(main())
    