"""FastAPI app: room creation, the game WebSocket, and the built frontend."""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .protocol import Join, client_message
from .rooms import RoomError, RoomManager, error_message

DEFAULT_STATIC = Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app(manager: RoomManager | None = None, static_dir: Path | None = None) -> FastAPI:
    manager = manager or RoomManager()
    static_dir = static_dir or Path(os.environ.get("CUNO_STATIC_DIR", DEFAULT_STATIC))

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async def sweeper() -> None:
            while True:
                await asyncio.sleep(60)
                manager.sweep()

        task = asyncio.create_task(sweeper())
        yield
        task.cancel()

    app = FastAPI(title="Cuno", lifespan=lifespan)
    app.state.manager = manager

    @app.post("/api/rooms")
    async def create_room() -> dict:
        return {"code": manager.create().code}

    @app.get("/api/rooms/{code}")
    async def room_info(code: str) -> dict:
        room = manager.get(code)
        if room is None:
            raise HTTPException(404, "No room with that code.")
        return {"code": room.code, "phase": room.phase, "players": len(room.players)}

    @app.websocket("/ws/{code}")
    async def game_socket(ws: WebSocket, code: str) -> None:
        await ws.accept()
        room = manager.get(code)
        if room is None:
            await ws.send_json(error_message("not_found", "No room with that code."))
            await ws.close()
            return
        try:
            try:
                first = client_message.validate_python(await ws.receive_json())
            except (ValidationError, ValueError):
                first = None
            if not isinstance(first, Join):
                await ws.send_json(error_message("not_joined", "Send a join message first."))
                await ws.close()
                return
            try:
                await room.join(ws, first.name, first.token)
            except RoomError as e:
                await ws.send_json(error_message(e.code, e.message))
                await ws.close()
                return
            while True:
                try:
                    raw = await ws.receive_json()
                except ValueError:
                    await ws.send_json(error_message("bad_message", "Malformed message."))
                    continue
                if isinstance(raw, dict) and raw.get("type") == "leave":
                    await room.leave(ws)
                    break
                await room.handle(ws, raw)
        except WebSocketDisconnect:
            pass
        finally:
            await room.disconnect(ws)

    if static_dir.is_dir():
        if (static_dir / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
        index = static_dir / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> FileResponse:
            candidate = (static_dir / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
