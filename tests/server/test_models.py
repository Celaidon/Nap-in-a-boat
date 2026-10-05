# Check C4: the ModelManager. Uses tiny fake files for download/checksum and a fake Llama.
import asyncio
import hashlib
import json
import threading
import time

import pytest

from src.server.generate import GenerationError
from src.server.models import MAX_WAITING, ModelManager
from src.server.settings import ROOT, Settings
from tests.server.conftest import collect

BLEND_IDS = ["sweep_000", "sweep_050", "sweep_100"]


def file_bytes(blend_id: str) -> bytes:
    return f"fake gguf content for {blend_id}".encode()


def make_registry() -> dict:
    registry = json.loads((ROOT / "contracts" / "mocks" / "registry.json").read_text())
    registry["blends"] = [b for b in registry["blends"] if b["id"] in BLEND_IDS]
    for blend in registry["blends"]:
        blend["sha256"] = hashlib.sha256(file_bytes(blend["id"])).hexdigest()
    return registry


class TrackingLlm:
    """Fake Llama that records overlapping generations and whether it was closed."""

    def __init__(self, name: str, n_tokens: int = 3, delay: float = 0.02):
        self.name, self.n_tokens, self.delay = name, n_tokens, delay
        self.closed = False
        self.calls: list[dict] = []  # kwargs of every create_chat_completion call
        self.active = 0
        self.max_active = 0
        self._guard = threading.Lock()

    def create_chat_completion(self, messages, max_tokens, temperature, stream):
        self.calls.append({"max_tokens": max_tokens, "temperature": temperature, "stream": stream})
        with self._guard:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            for i in range(min(self.n_tokens, max_tokens)):
                time.sleep(self.delay)
                yield {"choices": [{"delta": {"content": f"{self.name}{i} "}}]}
        finally:
            with self._guard:
                self.active -= 1

    def close(self):
        self.closed = True


class Harness:
    """A ModelManager wired to fakes, with a call log."""

    def __init__(self, tmp_path, corrupt=(), llm_tokens=3, **settings):
        self.downloads: list[str] = []
        self.loaded_llms: dict[str, TrackingLlm] = {}
        self.corrupt = set(corrupt)  # blend ids whose downloaded bytes are wrong
        self.llm_tokens = llm_tokens
        self.settings = Settings(_env_file=None, models_dir=str(tmp_path), **settings)
        self.manager = ModelManager(
            make_registry(), self.settings, loader=self.load, downloader=self.download
        )

    def download(self, key, dest):
        blend_id = key.split("/")[-1].removesuffix("-Q4_K_M.gguf")
        self.downloads.append(blend_id)
        dest.write_bytes(b"corrupted" if blend_id in self.corrupt else file_bytes(blend_id))

    def load(self, path):
        name = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].removesuffix("-Q4_K_M.gguf")
        llm = TrackingLlm(name, n_tokens=self.llm_tokens)
        self.loaded_llms[name] = llm
        return llm


def run(coro):
    return asyncio.run(coro)


async def touch(manager, *blend_ids):
    for blend_id in blend_ids:
        async with manager.use(blend_id):
            pass


# ---- eviction ---------------------------------------------------------------


def test_switching_between_three_blends_evicts_the_oldest(tmp_path):
    h = Harness(tmp_path, max_loaded_models=2)
    run(touch(h.manager, "sweep_000", "sweep_050", "sweep_100"))
    assert h.manager.loaded == ["sweep_050", "sweep_100"]
    assert h.loaded_llms["sweep_000"].closed  # memory released
    assert not h.loaded_llms["sweep_050"].closed


def test_recently_used_model_survives_eviction(tmp_path):
    h = Harness(tmp_path, max_loaded_models=2)
    run(touch(h.manager, "sweep_000", "sweep_050", "sweep_000", "sweep_100"))
    assert h.manager.loaded == ["sweep_000", "sweep_100"]  # sweep_050 was the least recently used
    assert len(h.loaded_llms) == 3 and h.loaded_llms["sweep_050"].closed


def test_model_in_use_is_never_evicted(tmp_path):
    h = Harness(tmp_path, max_loaded_models=1)

    async def go():
        release = asyncio.Event()

        async def holder():
            async with h.manager.use("sweep_000"):
                await release.wait()

        task = asyncio.create_task(holder())
        await asyncio.sleep(0.05)
        with pytest.raises(GenerationError) as info:
            await touch(h.manager, "sweep_050")  # the only slot is busy generating
        release.set()
        await task
        await touch(h.manager, "sweep_050")  # now there is room again
        return info.value

    err = run(go())
    assert err.code == "busy"
    assert h.manager.loaded == ["sweep_050"]


# ---- download and checksum --------------------------------------------------


def test_download_then_verified_file_is_kept_and_reused(tmp_path):
    h = Harness(tmp_path)
    run(touch(h.manager, "sweep_050"))
    run(touch(h.manager, "sweep_050"))
    assert h.downloads == ["sweep_050"]  # downloaded once
    assert (tmp_path / "sweep_050-Q4_K_M.gguf").read_bytes() == file_bytes("sweep_050")
    assert not list(tmp_path.glob("*.part"))


def test_wrong_checksum_after_download_is_rejected_and_deleted(tmp_path):
    h = Harness(tmp_path, corrupt={"sweep_050"})
    with pytest.raises(GenerationError) as info:
        run(touch(h.manager, "sweep_050"))
    assert info.value.code == "internal"
    assert "Checksum mismatch" in info.value.message
    assert not (tmp_path / "sweep_050-Q4_K_M.gguf").exists()
    assert h.loaded_llms == {}  # never loaded
    assert h.manager.loaded == []


def test_corrupt_file_already_on_disk_is_deleted_then_redownloaded_next_time(tmp_path):
    (tmp_path / "sweep_050-Q4_K_M.gguf").write_bytes(b"half a file")
    h = Harness(tmp_path)
    with pytest.raises(GenerationError, match="Checksum mismatch"):
        run(touch(h.manager, "sweep_050"))
    assert not (tmp_path / "sweep_050-Q4_K_M.gguf").exists()
    assert h.downloads == []

    run(touch(h.manager, "sweep_050"))  # the next request heals itself
    assert h.downloads == ["sweep_050"]
    assert h.manager.loaded == ["sweep_050"]


def test_download_failure_is_internal_error_and_leaves_no_partial_file(tmp_path):
    h = Harness(tmp_path)

    def broken(key, dest):
        dest.write_bytes(b"par")
        raise ConnectionError("spaces unreachable")

    h.manager.downloader = broken
    with pytest.raises(GenerationError, match="Download of sweep_050 failed") as info:
        run(touch(h.manager, "sweep_050"))
    assert info.value.code == "internal"
    assert list(tmp_path.iterdir()) == []


def test_load_failure_is_internal_and_not_cached(tmp_path):
    h = Harness(tmp_path)
    good_load = h.load
    h.manager.loader = lambda path: (_ for _ in ()).throw(OSError("bad gguf"))
    with pytest.raises(GenerationError, match="Could not load sweep_050") as info:
        run(touch(h.manager, "sweep_050"))
    assert info.value.code == "internal"
    assert h.manager.loaded == []

    h.manager.loader = good_load
    run(touch(h.manager, "sweep_050"))
    assert h.manager.loaded == ["sweep_050"]


def test_unknown_blend(tmp_path):
    h = Harness(tmp_path)
    with pytest.raises(GenerationError) as info:
        run(touch(h.manager, "sweep_999"))
    assert info.value.code == "unknown_blend"


def test_dev_override_shares_one_model_and_skips_download(tmp_path):
    h = Harness(tmp_path, dev_model_override=str(tmp_path / "tiny.gguf"))
    run(touch(h.manager, "sweep_000", "sweep_100"))
    assert h.downloads == []
    assert len(h.loaded_llms) == 1  # one file, one Llama, one lock
    assert h.manager.loaded == ["sweep_000", "sweep_100"]


# ---- concurrency ------------------------------------------------------------


def test_two_simultaneous_requests_on_one_model_take_turns(tmp_path):
    h = Harness(tmp_path)

    async def one(prompt):
        pieces = []
        async for text in h.manager.stream("sweep_050", prompt, 10, 0.0, threading.Event()):
            pieces.append(text)
        return pieces

    async def go():
        return await asyncio.gather(one("a"), one("b"))

    first, second = run(go())
    assert len(first) == 3 and len(second) == 3  # both finished
    assert h.loaded_llms["sweep_050"].max_active == 1  # never two generations at once


def test_queue_is_limited_and_extra_requests_get_busy(tmp_path):
    h = Harness(tmp_path)

    async def go():
        release = asyncio.Event()

        async def hold_or_wait(hold: bool):
            async with h.manager.use("sweep_050"):
                if hold:
                    await release.wait()
                return "ok"

        holder = asyncio.create_task(hold_or_wait(True))
        await asyncio.sleep(0.05)
        waiters = [asyncio.create_task(hold_or_wait(False)) for _ in range(MAX_WAITING)]
        await asyncio.sleep(0.05)
        with pytest.raises(GenerationError) as info:
            await hold_or_wait(False)  # one more than the queue allows
        release.set()
        return info.value, await asyncio.gather(holder, *waiters)

    err, results = run(go())
    assert err.code == "busy"
    assert results == ["ok"] * (1 + MAX_WAITING)  # the queued ones were served, in turn


def test_cancelled_waiter_does_not_leak_a_queue_slot(tmp_path):
    h = Harness(tmp_path)

    async def go():
        release = asyncio.Event()

        async def holder():
            async with h.manager.use("sweep_050"):
                await release.wait()

        async def waiter():
            async with h.manager.use("sweep_050"):
                pass

        hold = asyncio.create_task(holder())
        await asyncio.sleep(0.05)
        for _ in range(5):  # more cancellations than the queue holds
            task = asyncio.create_task(waiter())
            await asyncio.sleep(0.01)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        release.set()
        await hold
        await touch(h.manager, "sweep_050")  # the lock and queue still work

    run(go())


# ---- through the server -----------------------------------------------------


def attach_manager(client, h: Harness) -> None:
    client.app.state.manager = h.manager
    client.app.state.stream = h.manager.stream


def test_health_lists_loaded_blends(make_client, tmp_path):
    client = make_client()
    h = Harness(tmp_path)
    attach_manager(client, h)
    assert client.get("/health").json() == {"status": "ok", "loaded": []}
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "generate", "request_id": "r1", "blend_id": "sweep_050", "prompt": "hi"})
        assert collect(ws, "r1")[-1]["type"] == "done"
    assert client.get("/health").json() == {"status": "ok", "loaded": ["sweep_050"]}


def test_busy_error_reaches_the_client(make_client, tmp_path):
    client = make_client()
    h = Harness(tmp_path)
    attach_manager(client, h)
    total = 1 + MAX_WAITING + 2  # one running, the queue full, two too many
    with client.websocket_connect("/ws") as ws:
        for i in range(total):
            ws.send_json({"type": "generate", "request_id": f"r{i}", "blend_id": "sweep_050", "prompt": "hi"})
        outcomes = []
        while len(outcomes) < total:
            msg = ws.receive_json()
            if msg["type"] == "done":
                outcomes.append("done")
            elif msg["type"] == "error":
                outcomes.append(msg["code"])
    assert sorted(outcomes) == ["busy", "busy"] + ["done"] * (1 + MAX_WAITING)
    assert h.loaded_llms["sweep_050"].max_active == 1


def test_wrong_checksum_reaches_the_client_as_internal(make_client, tmp_path):
    client = make_client()
    attach_manager(client, Harness(tmp_path, corrupt={"sweep_050"}))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "generate", "request_id": "r1", "blend_id": "sweep_050", "prompt": "hi"})
        last = collect(ws, "r1")[-1]
    assert last["type"] == "error" and last["code"] == "internal"
    assert "Checksum mismatch" in last["message"]
