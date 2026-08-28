from __future__ import annotations

import queue
import threading
import time

from .host_thread import HostThread
from .lan_bus import VirtualLanBus
from .models import EventType, HostConfig, SimulationEvent
from .validators import normalize_ip, validate_host


DEFAULT_HOSTS = [
    HostConfig("host-1", "Host A", "192.168.1.10", "AA:BB:CC:00:00:01", 170, 145),
    HostConfig("host-2", "Host B", "192.168.1.20", "AA:BB:CC:00:00:02", 590, 145),
    HostConfig("host-3", "Host C", "192.168.1.30", "AA:BB:CC:00:00:03", 170, 445),
    HostConfig("host-4", "Host D", "192.168.1.40", "AA:BB:CC:00:00:04", 590, 445),
]


class SimulationController:
    def __init__(self, event_queue: queue.Queue[SimulationEvent] | None = None, delivery_delay: float = 1.4):
        self.events = event_queue or queue.Queue()
        self.configs: dict[str, HostConfig] = {h.host_id: h for h in DEFAULT_HOSTS}
        self.bus: VirtualLanBus | None = None
        self.hosts: dict[str, HostThread] = {}
        self.aging_seconds = 30.0
        self.delivery_delay = delivery_delay
        self.running = False
        self.paused = False
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self.bus = VirtualLanBus(self.delivery_delay)
            request_timeout = max(4.0, self.delivery_delay * 2 + 1.0)
            self.hosts = {
                host_id: HostThread(config, self.bus, self.events.put, self.aging_seconds, request_timeout)
                for host_id, config in self.configs.items()
            }
            for host in self.hosts.values():
                host.start()
            self.running, self.paused = True, False

    def pause(self) -> None:
        with self._lock:
            if not self.running:
                return
            self.paused = True
            for host in self.hosts.values():
                host.set_paused(True)

    def resume(self) -> None:
        with self._lock:
            if not self.running:
                return
            self.paused = False
            for host in self.hosts.values():
                host.set_paused(False)

    def stop(self) -> None:
        with self._lock:
            if self.bus:
                self.bus.close()
            for host in self.hosts.values():
                host.stop()
            for host in self.hosts.values():
                host.join(timeout=1.0)
            self.hosts.clear()
            self.bus = None
            self.running, self.paused = False, False

    def reset(self) -> None:
        self.stop()
        self.start()

    def set_aging_seconds(self, seconds: float) -> None:
        if not 5 <= seconds <= 120:
            raise ValueError("缓存老化时间应在 5～120 秒之间")
        self.aging_seconds = seconds
        for host in self.hosts.values():
            host.cache.aging_seconds = seconds

    def resolve(self, host_id: str, target_ip: str) -> str:
        if not self.running:
            raise RuntimeError("请先启动仿真")
        if self.paused:
            raise RuntimeError("仿真已暂停，请先继续")
        host = self.hosts.get(host_id)
        if host is None:
            raise ValueError("源主机不存在")
        target_ip = normalize_ip(target_ip)
        if target_ip == host.config.ip:
            return "SELF"
        return host.request_resolution(target_ip)

    def add_host(self, name: str, ip: str, mac: str) -> HostConfig:
        if len(self.configs) >= 6:
            raise ValueError("最多支持 6 台主机")
        name, ip, mac = validate_host(name, ip, mac)
        if any(h.ip == ip for h in self.configs.values()):
            raise ValueError("IP 地址已被使用")
        if any(h.mac == mac for h in self.configs.values()):
            raise ValueError("MAC 地址已被使用")
        index = len(self.configs) + 1
        extra_positions = {5: (105, 295), 6: (655, 295)}
        x, y = extra_positions[index]
        config = HostConfig(f"host-{index}", name, ip, mac, x, y)
        self.configs[config.host_id] = config
        if self.running:
            self.reset()
        return config

    def update_host(self, host_id: str, name: str, ip: str, mac: str) -> HostConfig:
        if host_id not in self.configs:
            raise ValueError("主机不存在")
        name, ip, mac = validate_host(name, ip, mac)
        for other_id, other in self.configs.items():
            if other_id != host_id and other.ip == ip:
                raise ValueError("IP 地址已被使用")
            if other_id != host_id and other.mac == mac:
                raise ValueError("MAC 地址已被使用")
        old = self.configs[host_id]
        config = HostConfig(host_id, name, ip, mac, old.x, old.y)
        self.configs[host_id] = config
        was_running = self.running
        if was_running:
            self.reset()
        return config

    def cache_snapshot(self, host_id: str):
        host = self.hosts.get(host_id)
        return host.cache.snapshot() if host else []

    def close(self) -> None:
        self.stop()
