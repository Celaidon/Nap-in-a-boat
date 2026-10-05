# Token streaming. llama-cpp-python is blocking, so inference runs in a worker thread
# and tokens come back to the event loop through an asyncio.Queue.
import asyncio
import os
import threading
from collections.abc import AsyncIterator

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
