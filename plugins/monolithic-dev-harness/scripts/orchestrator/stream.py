from collections import deque
from collections.abc import Callable

from .reducers import reduce_queue_state
from .state import Event, QueueState


class OrchestratorStream:
    """A reactive state container that manages the event stream and state transitions."""

    def __init__(self, initial_state: QueueState, *, max_retries: int = 3) -> None:
        self.state = initial_state
        self.max_retries = max_retries
        self.listeners: list[
            Callable[[QueueState, Event, OrchestratorStream], None]
        ] = []
        self._queue: deque[Event] = deque()
        self._dispatching = False

    def subscribe(
        self, listener: Callable[[QueueState, Event, "OrchestratorStream"], None]
    ) -> None:
        """Register a hook to listen for state changes and events."""
        self.listeners.append(listener)

    def dispatch(self, event: Event) -> None:
        """Process events via a queue so nested dispatches stay ordered and consistent."""
        self._queue.append(event)
        if self._dispatching:
            return

        self._dispatching = True
        try:
            while self._queue:
                current_event = self._queue.popleft()
                self.state = reduce_queue_state(
                    self.state, current_event, self.max_retries
                )
                for listener in list(self.listeners):
                    listener(self.state, current_event, self)
        finally:
            self._dispatching = False
