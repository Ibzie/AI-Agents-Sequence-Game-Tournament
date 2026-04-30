from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import sys
import os
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from AI.game_log import GameLog, GameStore, PlayerInfo
from AI.game_runner import GameConfig, run_game_in_thread

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"
LOGS_DIR = Path(__file__).resolve().parent / "logs"

app = FastAPI(title="Sequence Game Visualizer")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

store = GameStore(logs_dir=LOGS_DIR)


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: asyncio.Queue = asyncio.Queue()

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

    def broadcast_from_thread(self, message: str):
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._broadcast_internal(message), self._loop)

    async def _broadcast_internal(self, message: str):
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()
live_game_id: Optional[str] = None
live_events: list[dict] = []


class NewGameRequest(BaseModel):
    p1_provider: str = "ollama"
    p1_model: str = "llama3"
    p2_provider: str = "ollama"
    p2_model: str = "llama3"
    delay_ms: int = 500
    ollama_host: str = "http://localhost:11434"


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/games")
async def list_games():
    return store.list_games()


@app.get("/api/games/{game_id}")
async def get_game(game_id: str):
    try:
        game_log = store.load(game_id)
        return game_log.to_dict()
    except FileNotFoundError:
        return {"error": f"Game {game_id} not found"}, 404


@app.post("/api/games")
async def start_game(req: NewGameRequest):
    global live_game_id, live_events

    config = GameConfig(
        p1_provider=req.p1_provider,
        p1_model=req.p1_model,
        p2_provider=req.p2_provider,
        p2_model=req.p2_model,
        delay_ms=req.delay_ms,
        ollama_host=req.ollama_host,
    )

    game_log = GameLog(
        players=[
            PlayerInfo(id=config.p1_id, model=config.p1_model, provider=config.p1_provider, chip="blue"),
            PlayerInfo(id=config.p2_id, model=config.p2_model, provider=config.p2_provider, chip="green"),
        ]
    )

    live_game_id = game_log.game_id
    live_events = []

    game_log_for_save = game_log

    result_queue: queue.Queue = queue.Queue()

    def on_event(event_dict: dict):
        live_events.append(event_dict)
        payload = json.dumps({"type": "game_event", "game_id": game_log.game_id, "event": event_dict})
        manager.broadcast_from_thread(payload)
        if config.delay_ms > 0:
            import time
            time.sleep(config.delay_ms / 1000.0)

    def run():
        nonlocal game_log_for_save
        try:
            from AI.game_runner import _run_sync
            game_log_for_save = _run_sync(config, on_event)
            game_log_for_save.game_id = game_log.game_id
            result_queue.put(("done", game_log_for_save))
        except Exception as e:
            logger.exception(f"Game thread error: {e}")
            result_queue.put(("error", str(e)))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    async def wait_for_game():
        while result_queue.empty():
            await asyncio.sleep(0.5)
        result = result_queue.get()
        if result[0] == "done":
            gl = result[1]
            try:
                store.save(gl)
                payload = json.dumps({"type": "game_saved", "game_id": gl.game_id})
                await manager.broadcast(payload)
            except Exception as e:
                logger.error(f"Failed to save game log: {e}")
        else:
            payload = json.dumps({"type": "game_error", "error": result[1]})
            await manager.broadcast(payload)

    asyncio.create_task(wait_for_game())

    return {"game_id": game_log.game_id, "status": "started"}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        if live_events:
            await websocket.send_text(json.dumps({
                "type": "replay",
                "game_id": live_game_id,
                "events": live_events,
            }))

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    manager.set_loop(asyncio.get_event_loop())


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=8000)