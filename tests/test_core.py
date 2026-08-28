import queue
import time

from arp_simulator.cache import ArpCache
from arp_simulator.controller import SimulationController
from arp_simulator.lan_bus import VirtualLanBus
from arp_simulator.models import ArpOpcode, ArpPacket, CacheChange


def test_cache_lifecycle():
    now = [0.0]
    cache = ArpCache(aging_seconds=5, clock=lambda: now[0])
    _, change = cache.learn("192.168.1.2", "AA:BB:CC:00:00:02")
    assert change is CacheChange.NEW
    assert cache.lookup("192.168.1.2") is not None
    now[0] = 6
    assert cache.expire() and cache.lookup("192.168.1.2") is None


def test_bus_broadcast_and_unicast():
    bus = VirtualLanBus(delivery_delay=0)
    qa, qb = bus.register("a"), bus.register("b")
    packet = ArpPacket(1, ArpOpcode.REQUEST, "192.168.1.1", "AA:BB:CC:00:00:01", "192.168.1.2", "00:00:00:00:00:00", "a")
    assert bus.broadcast(packet) == 2
    assert qa.get_nowait() == packet and qb.get_nowait() == packet
    reply = ArpPacket(2, ArpOpcode.REPLY, "192.168.1.2", "AA:BB:CC:00:00:02", "192.168.1.1", "AA:BB:CC:00:00:01", "b", "a")
    assert bus.unicast(reply)
    assert qa.get_nowait() == reply
    assert qb.empty()


def test_arp_resolution_flow():
    controller = SimulationController(delivery_delay=0)
    controller.start()
    try:
        result = controller.resolve("host-1", "192.168.1.20")
        assert result == "BROADCAST"
        deadline = time.monotonic() + 2
        events = []
        while time.monotonic() < deadline:
            try:
                events.append(controller.events.get(timeout=0.05))
            except queue.Empty:
                pass
            if any(e.event_type.value == "CACHE_CHANGED" and e.host_id == "host-1" and e.payload.get("change") == "NEW" for e in events):
                break
        assert any(e.event_type.value == "PACKET_SENT" and e.payload["packet"].opcode is ArpOpcode.REPLY for e in events)
        assert controller.cache_snapshot("host-1")
        assert controller.resolve("host-1", "192.168.1.20") == "CACHE_HIT"
    finally:
        controller.close()


def test_pause_excludes_aging_time():
    controller = SimulationController(delivery_delay=0)
    controller.set_aging_seconds(5)
    controller.start()
    try:
        controller.hosts["host-1"].cache.learn("192.168.1.99", "AA:BB:CC:00:00:99")
        controller.pause()
        host = controller.hosts["host-1"]
        host._paused_at -= 10
        controller.resume()
        assert controller.cache_snapshot("host-1")
    finally:
        controller.close()
