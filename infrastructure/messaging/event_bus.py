"""
drone-detector/infrastructure/messaging/event_bus.py
Event Bus (Infrastructure Layer)

Tanggung jawab:
- Publish / subscribe event internal
- Decouple producer (pipeline) dari consumer (WS, logger, alert)
- Thread-safe dan synchronous by default

Tidak mengandung:
- FastAPI / WebSocket detail
- Detection logic
- Hardware detail
"""

import threading
from typing import Any, Callable, Dict, List


EventHandler = Callable[[Dict[str, Any]], None]


class EventBus:
    """
    Simple in-process publish/subscribe event bus.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._lock = threading.Lock()
        self._running = False

    # ---------- Lifecycle ----------

    def start(self) -> None:
        """
        Start event bus.
        """
        self._running = True

    def stop(self) -> None:
        """
        Stop event bus and clear subscribers.
        """
        self._running = False
        with self._lock:
            self._subscribers.clear()

    def is_running(self) -> bool:
        return self._running

    # ---------- Subscription ----------

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """
        Subscribe handler ke topic tertentu.
        """
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """
        Unsubscribe handler dari topic.
        """
        with self._lock:
            if topic in self._subscribers:
                self._subscribers[topic] = [
                    h for h in self._subscribers[topic] if h != handler
                ]
                if not self._subscribers[topic]:
                    del self._subscribers[topic]

    # ---------- Publish ----------

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Publish event ke semua subscriber topic.
        """
        if not self._running:
            return

        with self._lock:
            handlers = list(self._subscribers.get(topic, []))

        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                # Jangan biarkan satu subscriber merusak sistem
                self._handle_handler_error(topic, exc)

    # ---------- Error Handling ----------

    def _handle_handler_error(self, topic: str, exc: Exception) -> None:
        """
        Error isolation untuk subscriber.
        """
        # Untuk sekarang: silent fail
        # Bisa di-upgrade ke logging / system event
        pass
