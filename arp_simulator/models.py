from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time


class ArpOpcode(str, Enum):
    REQUEST = "REQUEST"
    REPLY = "REPLY"


class CacheChange(str, Enum):
    MISS = "MISS"
    NEW = "NEW"
    UPDATED = "UPDATED"
    HIT = "HIT"
    EXPIRED = "EXPIRED"


class EventType(str, Enum):
    PACKET_SENT = "PACKET_SENT"
    PACKET_RECEIVED = "PACKET_RECEIVED"
    CACHE_CHANGED = "CACHE_CHANGED"
    HOST_STATUS = "HOST_STATUS"
    ERROR = "ERROR"


@dataclass(frozen=True)
class HostConfig:
    host_id: str
    name: str
    ip: str
    mac: str
    x: float
    y: float


@dataclass(frozen=True)
class ArpPacket:
    packet_id: int
    opcode: ArpOpcode
    sender_ip: str
    sender_mac: str
    target_ip: str
    target_mac: str
    source_host_id: str
    destination_host_id: str | None = None
    created_at: float = field(default_factory=time.monotonic)


@dataclass
class ArpCacheEntry:
    ip: str
    mac: str
    learned_at: float
    last_seen: float
    state: CacheChange


@dataclass(frozen=True)
class SimulationEvent:
    event_type: EventType
    timestamp: float
    host_id: str
    payload: dict
