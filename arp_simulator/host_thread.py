from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

from .cache import ArpCache
from .lan_bus import VirtualLanBus
from .models import ArpOpcode, ArpPacket, EventType, HostConfig, SimulationEvent


class HostThread(threading.Thread):
    def __init__(self, config: HostConfig, bus: VirtualLanBus, emit: Callable[[SimulationEvent], None], aging_seconds: float = 30.0, request_timeout: float = 4.0):
        super().__init__(name=f"host-{config.host_id}", daemon=True)
        self.config = config
        self.bus = bus
        self.emit = emit
        self.inbox = bus.register(config.host_id)
        self.cache = ArpCache(aging_seconds)
        self.request_timeout = request_timeout
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.status = "IDLE"
        self._last_expire_check = 0.0
        self._pending: dict[str, tuple[int, float]] = {}
        self._paused_at: float | None = None

    def _event(self, event_type: EventType, payload: dict) -> None:
        self.emit(SimulationEvent(event_type, time.time(), self.config.host_id, payload))

    def set_paused(self, paused: bool) -> None:
        if paused:
            if self._paused_at is None:
                self._paused_at = time.monotonic()
            self.pause_event.clear()
            self.status = "PAUSED"
        else:
            if self._paused_at is not None:
                paused_for = time.monotonic() - self._paused_at
                self.cache.shift_timestamps(paused_for)
                self._pending = {
                    ip: (packet_id, started_at + paused_for)
                    for ip, (packet_id, started_at) in self._pending.items()
                }
                self._paused_at = None
            self.pause_event.set()
            self.status = "IDLE"
        self._event(EventType.HOST_STATUS, {"status": self.status})

    def stop(self) -> None:
        self.stop_event.set()
        self.pause_event.set()

    def request_resolution(self, target_ip: str) -> str:
        entry = self.cache.lookup(target_ip)
        if entry:
            self._event(EventType.CACHE_CHANGED, {"change": "HIT", "entry": entry})
            return "CACHE_HIT"
        if target_ip in self._pending:
            return "PENDING"
        self._event(EventType.CACHE_CHANGED, {"change": "MISS", "target_ip": target_ip})
        packet = ArpPacket(self.bus.next_packet_id(), ArpOpcode.REQUEST, self.config.ip, self.config.mac, target_ip, "00:00:00:00:00:00", self.config.host_id)
        self._pending[target_ip] = (packet.packet_id, time.monotonic())
        self.status = "BROADCASTING"
        self._event(EventType.HOST_STATUS, {"status": self.status})
        count = self.bus.broadcast(packet)
        self._event(EventType.PACKET_SENT, {"packet": packet, "mode": "broadcast", "recipients": count})
        return "BROADCAST"

    def run(self) -> None:
        try:
            while not self.stop_event.is_set():
                if not self.pause_event.wait(0.1):
                    continue
                now = time.monotonic()
                if now - self._last_expire_check >= 0.2:
                    for entry in self.cache.expire(now):
                        self._event(EventType.CACHE_CHANGED, {"change": "EXPIRED", "entry": entry})
                    self._last_expire_check = now
                for target_ip, (packet_id, started_at) in list(self._pending.items()):
                    if now - started_at >= self.request_timeout:
                        del self._pending[target_ip]
                        self.status = "TIMEOUT"
                        self._event(EventType.HOST_STATUS, {"status": self.status})
                        self._event(EventType.ERROR, {"message": f"ARP 请求 #{packet_id} 超时，未找到目标主机"})
                        self.status = "IDLE"
                try:
                    packet = self.inbox.get(timeout=0.1)
                except queue.Empty:
                    continue
                self._handle_packet(packet)
        finally:
            self.bus.unregister(self.config.host_id)

    def _handle_packet(self, packet: ArpPacket) -> None:
        self._event(EventType.PACKET_RECEIVED, {"packet": packet, "mode": "broadcast" if packet.destination_host_id is None else "unicast"})
        if packet.sender_ip == self.config.ip and packet.sender_mac == self.config.mac:
            return
        entry, change = self.cache.learn(packet.sender_ip, packet.sender_mac)
        self._event(EventType.CACHE_CHANGED, {"change": change.value, "entry": entry})
        if packet.opcode is ArpOpcode.REQUEST and packet.target_ip == self.config.ip:
            reply = ArpPacket(self.bus.next_packet_id(), ArpOpcode.REPLY, self.config.ip, self.config.mac, packet.sender_ip, packet.sender_mac, self.config.host_id, packet.source_host_id)
            self.status = "REPLYING"
            self._event(EventType.HOST_STATUS, {"status": self.status})
            self.bus.unicast(reply)
            self._event(EventType.PACKET_SENT, {"packet": reply, "mode": "unicast", "recipients": 1})
            self.status = "IDLE"
        elif packet.opcode is ArpOpcode.REPLY and packet.destination_host_id == self.config.host_id:
            self._pending.pop(packet.sender_ip, None)
            self.status = "RESOLVED"
            self._event(EventType.HOST_STATUS, {"status": self.status})
            self.status = "IDLE"
