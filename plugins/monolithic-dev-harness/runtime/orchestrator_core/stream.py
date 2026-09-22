from __future__ import annotations

from collections import deque
from typing import Callable, List

from .reducers import reduce_queue_state
from .state import Event, QueueState


class OrchestratorStream:
    """Event stream with queued dispatch to avoid re-entrancy bugs."""

    def __init__(self, initial_state: QueueState, *, max_retries: int = 3) -> None:
        self.state = initial_state
        self.max_retries = max_retries
        self.listeners: List[Callable[[QueueState, Event, OrchestratorStream], None]] = []
        self._queue: deque[Event] = deque()
        self._dispatching = False

    def subscribe(self, listener: Callable[[QueueState, Event, OrchestratorStream], None]) -> None:
        self.listeners.append(listener)

    def dispatch(self, event: Event) -> None:
        self._queue.append(event)
        if self._dispatching:
            return
        self._dispatching = True
        try:
            while self._queue:
                current_event = self._queue.popleft()
                self.state = reduce_queue_state(self.state, current_event, self.max_retries)
                for listener in list(self.listeners):
                    listener(self.state, current_event, self)
        finally:
            self._dispatching = False
