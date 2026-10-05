# The /ws endpoint: message routing, per-request tasks, ping/pong (contract 4.4).
import asyncio
import json
import threading
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from src.server import finder
from src.server.generate import GenerationError

router = APIRouter()

DEFAULT_MAX_TOKENS = 256
DEFAULT_TEMPERATURE = 0.7
MAX_TOKENS_CAP = 2048  # protects the server; the model context is 4096


class BadRequest(Exception):
    """A client message that breaks the protocol."""


@dataclass
class ActiveRequest:
    task: asyncio.Task
    stop: threading.Event = field(default_factory=threading.Event)


class Connection:
    """One websocket client: serialises sends and tracks its running requests."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.app = ws.app
        self.active: dict[str, ActiveRequest] = {}
        self.last_seen = time.monotonic()
        self._send_lock = asyncio.Lock()

    async def send(self, message: dict) -> None:
        # Several request tasks share one socket, so sends take turns.
        async with self._send_lock:
            try:
                await self.ws.send_text(json.dumps(message))
            except (WebSocketDisconnect, RuntimeError):
                pass  # client is gone; the receive loop notices and cleans up

    async def error(self, request_id: str, code: str, message: str) -> None:
        await self.send({"type": "error", "request_id": request_id, "code": code, "message": message})

    # ---- handlers -------------------------------------------------------

    async def on_generate(self, msg: dict) -> None:
        request_id = msg["request_id"]
        blend_ids = {b["id"] for b in self.app.state.registry["blends"]}
        if msg["blend_id"] not in blend_ids:
            await self.error(request_id, "unknown_blend", f"No blend called {msg['blend_id']}")
            return
        if request_id in self.active:
            raise BadRequest(f"request_id {request_id} is already running")

        max_tokens = msg.get("max_tokens", DEFAULT_MAX_TOKENS)
        temperature = msg.get("temperature", DEFAULT_TEMPERATURE)
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise BadRequest("max_tokens must be an integer of at least 1")
        if isinstance(temperature, bool) or not isinstance(temperature, int | float) or temperature < 0:
            raise BadRequest("temperature must be a number of at least 0")

        self.start(
            request_id,
            lambda stop: self.run_generate(
                request_id, msg["blend_id"], msg["prompt"], min(max_tokens, MAX_TOKENS_CAP), temperature, stop
            ),
        )

    def start(self, request_id: str, make_coroutine) -> None:
        """Run a request as its own task so the receive loop stays free for cancel and pong."""
        stop = threading.Event()
        self.active[request_id] = ActiveRequest(asyncio.create_task(make_coroutine(stop)), stop)

    async def run_generate(self, request_id, blend_id, prompt, max_tokens, temperature, stop) -> None:
        count = 0
        first_token_at = 0.0
        try:
            async for text in self.app.state.stream(blend_id, prompt, max_tokens, temperature, stop):
                count += 1
                if count == 1:
                    first_token_at = time.monotonic()  # speed excludes model load and prompt processing
                await self.send({"type": "token", "request_id": request_id, "text": text})
            # Speed = tokens after the first / time since the first (0 if too few tokens to tell).
            elapsed = time.monotonic() - first_token_at
            speed = (count - 1) / elapsed if count > 1 and elapsed > 0 else 0.0
            await self.send({
                "type": "done", "request_id": request_id, "blend_id": blend_id,
                "tokens": count, "tokens_per_sec": round(speed, 2),
            })
        except GenerationError as exc:
            await self.error(request_id, exc.code, exc.message)
        except asyncio.CancelledError:
            raise  # cancel() or disconnect; whoever cancelled us reports it
        except Exception as exc:  # noqa: BLE001  never let one request kill the connection
            await self.error(request_id, "internal", f"{type(exc).__name__}: {exc}")
        finally:
            stop.set()
            self.active.pop(request_id, None)

    async def on_cancel(self, msg: dict) -> None:
        request = self.active.get(msg["request_id"])
        if request is None:
            return  # already finished (a normal race between done and cancel), nothing to stop
        await self.stop_request(msg["request_id"], request)
        await self.error(msg["request_id"], "cancelled", "Request was cancelled")

    async def stop_request(self, request_id: str, request: ActiveRequest) -> None:
        request.stop.set()  # lets worker threads (C3) stop quickly
        request.task.cancel()
        await asyncio.gather(request.task, return_exceptions=True)
        self.active.pop(request_id, None)

    async def stop_all(self) -> None:
        for request_id, request in list(self.active.items()):
            await self.stop_request(request_id, request)

    # ---- routing --------------------------------------------------------

    async def handle(self, raw: str | None) -> None:
        request_id = ""
        try:
            if raw is None:
                raise BadRequest("Only text messages are accepted")
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                raise BadRequest("Message is not valid JSON") from None
            if not isinstance(msg, dict) or not isinstance(msg.get("type"), str):
                raise BadRequest("Message must be a JSON object with a string 'type'")

            if isinstance(msg.get("request_id"), str):
                request_id = msg["request_id"]
            kind = msg["type"]

            if kind == "pong":
                return
            if kind not in ("generate", "cancel", "find_best"):
                raise BadRequest(f"Unknown message type '{kind}'")
            if not request_id:
                raise BadRequest("'request_id' (string) is required")
            required = {"generate": ("blend_id", "prompt"), "cancel": (), "find_best": ("tasks",)}[kind]
            for name in required:
                if name not in msg:
                    raise BadRequest(f"Missing field '{name}'")

            if kind == "generate":
                if not isinstance(msg["blend_id"], str) or not isinstance(msg["prompt"], str):
                    raise BadRequest("'blend_id' and 'prompt' must be strings")
                await self.on_generate(msg)
            elif kind == "cancel":
                await self.on_cancel(msg)
            else:
                await self.on_find_best(msg)
        except BadRequest as exc:
            await self.error(request_id, "bad_request", str(exc))

    async def on_find_best(self, msg: dict) -> None:
        request_id = msg["request_id"]
        if request_id in self.active:
            raise BadRequest(f"request_id {request_id} is already running")
        try:
            tasks = finder.validate_tasks(msg["tasks"])
        except GenerationError as exc:
            raise BadRequest(exc.message) from None
        self.start(request_id, lambda stop: self.run_find_best(request_id, tasks, stop))

    async def run_find_best(self, request_id: str, tasks: list, stop: threading.Event) -> None:
        async def progress(step: int, of: int, blend_id: str) -> None:
            await self.send(
                {"type": "progress", "request_id": request_id, "step": step, "of": of, "blend_id": blend_id}
            )

        try:
            best, scores = await finder.find_best(self.app, tasks, stop, progress)
            await self.send({"type": "result", "request_id": request_id, "best_blend_id": best, "scores": scores})
        except GenerationError as exc:
            await self.error(request_id, exc.code, exc.message)
        except asyncio.CancelledError:
            raise  # cancel() or disconnect; whoever cancelled us reports it
        except Exception as exc:  # noqa: BLE001  never let one request kill the connection
            await self.error(request_id, "internal", f"{type(exc).__name__}: {exc}")
        finally:
            stop.set()
            self.active.pop(request_id, None)

    # ---- keep-alive -----------------------------------------------------

    async def keep_alive(self, interval: float, timeout: float) -> None:
        """Ping every `interval` seconds; close the socket if the client is silent for `timeout`."""
        while True:
            await asyncio.sleep(interval)
            if time.monotonic() - self.last_seen > timeout:
                await self.ws.close(code=1011)
                return
            await self.send({"type": "ping"})


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    conn = Connection(ws)
    settings = ws.app.state.settings
    pinger = asyncio.create_task(conn.keep_alive(settings.ping_interval_s, settings.pong_timeout_s))
    try:
        while True:
            event = await ws.receive()
            if event["type"] == "websocket.disconnect":
                break
            conn.last_seen = time.monotonic()  # any client traffic proves it is alive
            await conn.handle(event.get("text"))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        pinger.cancel()
        await conn.stop_all()
