from __future__ import annotations

import ipaddress
import re

MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def normalize_ip(value: str) -> str:
    return str(ipaddress.IPv4Address(value.strip()))


def normalize_mac(value: str) -> str:
    value = value.strip().replace("-", ":").upper()
    if not MAC_RE.fullmatch(value):
        raise ValueError("MAC 地址应为 AA:BB:CC:DD:EE:FF 格式")
    return value


def validate_name(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 24:
        raise ValueError("主机名称长度应为 1～24 个字符")
    return value


def validate_host(name: str, ip: str, mac: str) -> tuple[str, str, str]:
    return validate_name(name), normalize_ip(ip), normalize_mac(mac)
