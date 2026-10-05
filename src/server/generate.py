# Token streaming. llama-cpp-python is blocking, so inference runs in a worker thread
# and tokens come back to the event loop through an asyncio.Queue.
import asyncio
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

FAKE_SENTENCE = "Soft rain falls on quiet rooftops while the whole city sleeps and dreams of morning light"
FAKE_DELAY_S = 0.02
N_CTX = 4096


class GenerationError(Exception):
    """A failure that maps onto a protocol error code (busy, internal, ...)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def fake_stream(
    blend_id: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    stop_event: threading.Event,
) -> AsyncIterator[str]:
    """Yield the words of a fixed sentence with a short delay. No model needed."""
    for word in FAKE_SENTENCE.split()[:max_tokens]:
        if stop_event.is_set():
            return
        await asyncio.sleep(FAKE_DELAY_S)
        yield word + " "


async def stream_tokens(
    llm, messages: list[dict], max_tokens: int, temperature: float, stop_event: threading.Event
) -> AsyncIterator[str]:
    """Run llm.create_chat_completion(stream=True) in a thread and yield its text pieces.

    The thread checks `stop_event` after every token, so setting it (cancel, disconnect)
    ends generation within one token. A failure inside the thread is re-raised here.

    This generator only finishes once the thread has really stopped. Callers hold the model's
    lock while iterating, and a Llama object must never run two generations at once.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    finished = asyncio.Event()
    done = object()

    def call_loop(fn, *args) -> None:
        try:
            loop.call_soon_threadsafe(fn, *args)
        except RuntimeError:
            pass  # the loop is already closed (server shutting down)

    def worker() -> None:
        try:
            chunks = llm.create_chat_completion(
                messages=messages, max_tokens=max_tokens, temperature=temperature, stream=True
            )
            try:
                for chunk in chunks:
                    if stop_event.is_set():
                        break
                    text = chunk["choices"][0]["delta"].get("content")
                    if text:
                        call_loop(queue.put_nowait, text)
            finally:
                chunks.close()  # make sure llama-cpp releases its generation state
        except Exception as exc:  # noqa: BLE001  forwarded to the async side below
            call_loop(queue.put_nowait, exc)
        finally:
            call_loop(queue.put_nowait, done)
            call_loop(finished.set)

    threading.Thread(target=worker, daemon=True, name="llm-worker").start()
    try:
        while (item := await queue.get()) is not done:
            if isinstance(item, Exception):
                raise GenerationError("internal", f"{type(item).__name__}: {item}")
            yield item
    finally:
        stop_event.set()  # consumer left early (cancel/disconnect): stop the thread too
        await finished.wait()


def load_llama(model_path: str):
    """Load a GGUF file with llama-cpp-python. Imported lazily so tests need no model."""
    from llama_cpp import Llama

    return Llama(model_path=model_path, n_ctx=N_CTX, n_threads=os.cpu_count(), verbose=False)


# ---- Best Blend Finder helpers ----------------------------------------------

FINDER_MAX_TOKENS = 512


class Cancelled(Exception):
    """Raised inside a worker thread when its request was cancelled."""


def make_generate(llm, stop_event: threading.Event, max_tokens: int = FINDER_MAX_TOKENS):
    """Build the `generate(prompt) -> str` function that score_tasks receives.

    Greedy (temperature 0) and returns the full answer at once. Internally it reads the
    stream so a cancel stops it within one token. Blocking: call it from a worker thread.
    """

    def generate(prompt: str) -> str:
        chunks = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0,
            stream=True,
        )
        pieces = []
        try:
            for chunk in chunks:
                if stop_event.is_set():
                    raise Cancelled
                text = chunk["choices"][0]["delta"].get("content")
                if text:
                    pieces.append(text)
        finally:
            chunks.close()
        return "".join(pieces)

    return generate


@asynccontextmanager
async def fake_session(blend_id: str, stop_event: threading.Event):
    """Stand-in for ModelManager.session when FAKE_GENERATOR is on: answers are instant."""
    yield lambda prompt: f"{blend_id}: {FAKE_SENTENCE}"


async def run_blocking(fn, *args):
    """Run fn(*args) in a thread. If we are cancelled, still wait for the thread to end.

    The caller's stop_event makes the thread quit quickly. Waiting matters because the
    model lock is released right after, and a Llama must never be used by two threads.
    """
    future = asyncio.ensure_future(asyncio.to_thread(fn, *args))
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        await asyncio.gather(future, return_exceptions=True)
        raise
