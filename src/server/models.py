# ModelManager: download from Spaces, verify SHA-256, load, LRU-cache, and lock per model.
import asyncio
import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from src.server.generate import (
    GenerationError,
    load_llama,
    make_generate,
    stream_tokens,
)
from src.server.settings import Settings

log = logging.getLogger("blendlab.models")

MAX_WAITING = 2  # requests allowed to queue behind a busy model; more get `busy`


@dataclass
class Entry:
    """One loaded model. With DEV_MODEL_OVERRIDE several blend ids share one entry."""

    llm: object
    blend_ids: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)  # one generation at a time
    users: int = 0  # requests holding or waiting for the lock; such an entry is never evicted
    waiting: int = 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def spaces_downloader(settings: Settings) -> Callable[[str, Path], None]:
    """Build a function that downloads one object from the private Spaces bucket."""

    def download(key: str, dest: Path) -> None:
        if not (settings.do_spaces_key and settings.do_spaces_secret):
            raise GenerationError("internal", "Model file is missing and Spaces credentials are not set")
        import boto3  # imported here: only needed when a download actually happens

        s3 = boto3.client(
            "s3",
            region_name=settings.do_spaces_region,
            endpoint_url=f"https://{settings.do_spaces_region}.digitaloceanspaces.com",
            aws_access_key_id=settings.do_spaces_key,
            aws_secret_access_key=settings.do_spaces_secret,
        )
        s3.download_file(settings.do_spaces_bucket, key, str(dest))

    return download


class ModelManager:
    def __init__(
        self,
        registry: dict,
        settings: Settings,
        loader: Callable[[str], object] = load_llama,
        downloader: Callable[[str, Path], None] | None = None,
    ):
        self.blends = {b["id"]: b for b in registry["blends"]}
        self.settings = settings
        self.loader = loader
        self.downloader = downloader or spaces_downloader(settings)
        self.max_loaded = max(1, settings.max_loaded_models)
        self.models_dir = settings.resolve(settings.models_dir)
        self._entries: OrderedDict[str, Entry] = OrderedDict()  # oldest first = LRU order
        self._load_lock = asyncio.Lock()  # loads happen one at a time (memory, disk, CPU)
        self._verified: set[Path] = set()  # files whose checksum was checked in this process

    @property
    def loaded(self) -> list[str]:
        """Blend ids currently in memory, for GET /health."""
        return sorted({b for e in self._entries.values() for b in e.blend_ids})

    # ---- public API -----------------------------------------------------

    async def stream(
        self, blend_id: str, prompt: str, max_tokens: int, temperature: float, stop_event: threading.Event
    ) -> AsyncIterator[str]:
        """Same signature as generate.fake_stream, so the websocket does not care which it gets."""
        messages = [{"role": "user", "content": prompt}]
        async with self.use(blend_id) as llm:
            async for text in stream_tokens(llm, messages, max_tokens, temperature, stop_event):
                yield text

    @asynccontextmanager
    async def session(self, blend_id: str, stop_event: threading.Event):
        """Hold a blend's model for a whole scoring run; yields a blocking generate(prompt) -> str."""
        async with self.use(blend_id) as llm:
            yield make_generate(llm, stop_event)

    @asynccontextmanager
    async def use(self, blend_id: str):
        """Yield the Llama for a blend while holding its lock. Waits briefly, else raises `busy`."""
        entry = await self._acquire_entry(blend_id)  # users already incremented
        try:
            if entry.lock.locked() and entry.waiting >= MAX_WAITING:
                raise GenerationError("busy", f"{blend_id} is busy with other requests, try again shortly")
            entry.waiting += 1
            try:
                await entry.lock.acquire()
            finally:
                entry.waiting -= 1
            try:
                yield entry.llm
            finally:
                entry.lock.release()
        finally:
            entry.users -= 1

    # ---- loading --------------------------------------------------------

    def _key(self, blend_id: str) -> str:
        # With a dev override every blend is the same file, so they share one Llama and one lock.
        return self.settings.dev_model_override or blend_id

    async def _acquire_entry(self, blend_id: str) -> Entry:
        if blend_id not in self.blends:
            raise GenerationError("unknown_blend", f"No blend called {blend_id}")
        key = self._key(blend_id)

        entry = self._entries.get(key)
        if entry is None:
            async with self._load_lock:
                entry = self._entries.get(key)  # someone may have loaded it while we waited
                if entry is None:
                    entry = await self._load(blend_id, key)
        entry.blend_ids.add(blend_id)
        self._entries.move_to_end(key)  # most recently used goes last
        entry.users += 1  # no await since we got the entry, so it cannot be evicted before this
        return entry

    async def _load(self, blend_id: str, key: str) -> Entry:
        path = await self._ensure_file(blend_id)
        self._make_room()
        started = time.monotonic()
        try:
            llm = await asyncio.to_thread(self.loader, str(path))
        except Exception as exc:
            raise GenerationError("internal", f"Could not load {blend_id}: {exc}") from exc
        log.info("loaded %s from %s in %.1fs", blend_id, path.name, time.monotonic() - started)
        entry = Entry(llm)
        self._entries[key] = entry
        return entry

    def _make_room(self) -> None:
        """Evict least-recently-used idle models until there is a free slot."""
        while len(self._entries) >= self.max_loaded:
            victim = next((k for k, e in self._entries.items() if e.users == 0), None)
            if victim is None:
                raise GenerationError("busy", "All model slots are in use, try again shortly")
            entry = self._entries.pop(victim)
            if hasattr(entry.llm, "close"):
                entry.llm.close()
            log.info("evicted %s", sorted(entry.blend_ids))

    async def _ensure_file(self, blend_id: str) -> Path:
        """Return the local GGUF path: downloaded if missing, checksum-verified once per process."""
        if self.settings.dev_model_override:
            return Path(self.settings.dev_model_override)  # dev stand-in model: no registry hash applies

        blend = self.blends[blend_id]
        path = self.models_dir / PurePosixPath(blend["gguf_key"]).name  # basename only: no path tricks
        if not path.exists():
            await self._download(blend, path)
        if path not in self._verified:
            started = time.monotonic()
            digest = await asyncio.to_thread(sha256_file, path)
            if digest != blend["sha256"].lower():
                path.unlink(missing_ok=True)
                log.error("checksum mismatch for %s, deleted %s", blend_id, path.name)
                raise GenerationError("internal", f"Checksum mismatch for {blend_id}; the file was deleted")
            log.info("verified %s in %.1fs", blend_id, time.monotonic() - started)
            self._verified.add(path)
        return path

    async def _download(self, blend: dict, path: Path) -> None:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + ".part")
        started = time.monotonic()
        try:
            await asyncio.to_thread(self.downloader, blend["gguf_key"], partial)
        except GenerationError:
            raise
        except Exception as exc:
            partial.unlink(missing_ok=True)
            raise GenerationError("internal", f"Download of {blend['id']} failed: {exc}") from exc
        os.replace(partial, path)  # a half-downloaded file never has the final name
        log.info("downloaded %s in %.1fs", blend["id"], time.monotonic() - started)
