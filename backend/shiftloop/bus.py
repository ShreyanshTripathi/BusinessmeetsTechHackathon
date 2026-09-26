"""In-process publish/subscribe bus.

Handlers run synchronously in subscription order, which keeps the pipeline deterministic and testable.
The API layer drives it from an asyncio task; swap for Redis Streams or Kafka when agents run as services.
"""
from collections import defaultdict
from typing import Any, Callable

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)

    def publish(self, topic: str, message: Any) -> None:
        for handler in list(self._handlers[topic]):
            handler(message)
