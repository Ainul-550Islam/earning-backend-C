# api/publisher_tools/fraud_prevention/device_fingerprint.py
"""Device Fingerprint — Device identification and emulator detection."""
import hashlib
from typing import Dict


def generate_device_fingerprint(device_data: dict) -> str:
    """Device fingerprint generate করে।"""
    components = [
        device_data.get("device_model", ""),
        device_data.get("device_os", ""),
        device_data.get("screen_resolution", ""),
        device_data.get("user_agent", ""),
        device_data.get("timezone", ""),
        device_data.get("language", ""),
    ]
    fp_string = "|".join(str(c) for c in components)
    return hashlib.sha256(fp_string.encode()).hexdigest()


def detect_emulator(device_data: dict) -> Dict:
    """Emulator/virtual device detection।"""
    score = 0
    signals = []
    model = device_data.get("device_model", "").lower()
    name  = device_data.get("device_name", "").lower()
    os    = device_data.get("device_os", "").lower()

    emulator_keywords = ["emulator", "sdk", "genymotion", "vbox", "virtual", "bluestacks", "nox", "memu", "ldplayer", "android_x86"]
    for kw in emulator_keywords:
        if kw in model or kw in name:
            score += 70; signals.append(f"emulator_keyword:{kw}")
            break

    # Suspicious hardware
    if device_data.get("cpu_cores", 4) > 16:
        score += 20; signals.append("too_many_cpu_cores")
    if device_data.get("ram_gb", 4) > 32:
        score += 20; signals.append("too_much_ram")

    # Missing hardware identifiers
    if not device_data.get("device_id"):
        score += 30; signals.append("missing_device_id")
    if not device_data.get("mac_address"):
        score += 10; signals.append("missing_mac_address")

    # Rooted/jailbroken
    if device_data.get("is_rooted", False):
        score += 25; signals.append("rooted_device")
    if device_data.get("is_jailbroken", False):
        score += 25; signals.append("jailbroken_device")

    return {"is_emulator": score >= 50, "score": min(100, score), "signals": signals}


def check_device_farm(device_fingerprints: list, ip: str) -> bool:
    """Same IP-এ multiple unique devices = device farm।"""
    from django.core.cache import cache
    key = f"device_farm:{ip}"
    devices = cache.get(key, set())
    if not isinstance(devices, set):
        devices = set()
    for fp in device_fingerprints:
        devices.add(fp)
    cache.set(key, devices, 3600)
    return len(devices) > 10


def get_device_trust_score(device_data: dict) -> int:
    """Device trust score (0-100, 100=most trusted)。"""
    score = 100
    emul = detect_emulator(device_data)
    score -= emul["score"] // 2
    if device_data.get("is_vpn"):   score -= 20
    if device_data.get("is_proxy"): score -= 25
    if device_data.get("is_tor"):   score -= 40
    return max(0, score)
