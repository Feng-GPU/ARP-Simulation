from __future__ import annotations

import queue
import threading

from .models import ArpPacket


class VirtualLanBus:
    """A shared broadcast medium represented by one receive queue per host."""

    def __init__(self, delivery_delay: float = 1.4):
        self._queues: dict[str, queue.Queue[ArpPacket]] = {}
        self._lock = threading.RLock()
        self._packet_id = 0
        self.delivery_delay = delivery_delay
        self._timers: list[threading.Timer] = []
        self._closed = False

    def register(self, host_id: str) -> queue.Queue[ArpPacket]:
        with self._lock:
            if host_id in self._queues:
                raise ValueError(f"主机已注册: {host_id}")
            q: queue.Queue[ArpPacket] = queue.Queue()
            self._queues[host_id] = q
            return q

    def unregister(self, host_id: str) -> None:
        with self._lock:
            self._queues.pop(host_id, None)

    def next_packet_id(self) -> int:
        with self._lock:
            self._packet_id += 1
            return self._packet_id

    def broadcast(self, packet: ArpPacket) -> int:
        with self._lock:
            queues = list(self._queues.values())
        self._deliver_later(lambda: [q.put(packet) for q in queues])
        return len(queues)

    def unicast(self, packet: ArpPacket) -> bool:
        with self._lock:
            q = self._queues.get(packet.destination_host_id or "")
        if q is None:
            return False
        self._deliver_later(lambda: q.put(packet))
        return True

    def _deliver_later(self, delivery) -> None:
        if self.delivery_delay <= 0:
            delivery()
            return

        def run():
            try:
                with self._lock:
                    if self._closed:
                        return
                delivery()
            finally:
                with self._lock:
                    if timer in self._timers:
                        self._timers.remove(timer)

        timer = threading.Timer(self.delivery_delay, run)
        timer.daemon = True
        with self._lock:
            if self._closed:
                return
            self._timers.append(timer)
        timer.start()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            timers = list(self._timers)
            self._timers.clear()
        for timer in timers:
            timer.cancel()

    def host_count(self) -> int:
        with self._lock:
            return len(self._queues)
