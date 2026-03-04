"""In-memory progress queue for streaming scrape events to the browser via SSE."""
import asyncio

_queues: dict[str, asyncio.Queue] = {}
_active: set[str] = set()


def start(bot_id: str):
    _queues[bot_id] = asyncio.Queue()
    _active.add(bot_id)


def is_active(bot_id: str) -> bool:
    return bot_id in _active


async def push(bot_id: str, url: str, status: str):
    if bot_id in _queues:
        await _queues[bot_id].put({"url": url, "status": status})


async def finish(bot_id: str, article_count: int = 0):
    if bot_id in _queues:
        await _queues[bot_id].put({"done": True, "article_count": article_count})
    _active.discard(bot_id)


async def get_event(bot_id: str, timeout: float = 60):
    if bot_id not in _queues:
        return None
    try:
        return await asyncio.wait_for(_queues[bot_id].get(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"timeout": True}


def cleanup(bot_id: str):
    _queues.pop(bot_id, None)
    _active.discard(bot_id)
