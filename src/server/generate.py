# Token streaming. C2 ships a fake generator; C3 adds the real llama-cpp one in this file.
import asyncio
import threading
from collections.abc import AsyncIterator

FAKE_SENTENCE = "Soft rain falls on quiet rooftops while the whole city sleeps and dreams of morning light"
FAKE_DELAY_S = 0.02


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
