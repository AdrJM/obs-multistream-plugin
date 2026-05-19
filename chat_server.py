import asyncio
import os
import websockets.server
import json
from datetime import datetime, timezone
import argparse

connected_clients = set()
_log_file = None
STATUS_PATH = os.path.join(os.path.dirname(__file__), "config", "status.json")

def is_platform_active(platform: str) -> bool:
    try:
        with open(STATUS_PATH, "r") as f:
            status = json.load(f)
        return status.get(platform, {}).get("active", False)
    except Exception:
        return False
    
async def ws_handler(websocket):
    connected_clients.add(websocket)
    print(f"Nowy klient ({len(connected_clients)} łącznie)")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"Klient rozłączony ({len(connected_clients)} łączenie)")
    
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

    os.makedirs(args.logs_path, exist_ok = True)
    stream_start = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(args.logs_path, f"{stream_start}_stream.jsonl")
    _log_file = open(log_path, "w", encoding = "utf-8")
    print(f"Plik logu: {log_path}")

    async with websockets.serve(ws_handler, "localhost", 5001):
        print("WebSocket gotowy na ws://localhost:5001")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
    