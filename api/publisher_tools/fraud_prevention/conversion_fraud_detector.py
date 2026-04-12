# api/publisher_tools/fraud_prevention/conversion_fraud_detector.py
"""Conversion Fraud Detector — Install hijacking, fake conversions."""
from typing import Dict
from django.core.cache import cache


def detect_conversion_fraud(context: dict) -> Dict:
    """Conversion fraud detection।"""
    score = 0
    signals = []
    device_id = context.get("device_id", "")
    ip = context.get("ip_address", "")
    offer_id = context.get("offer_id", "")

    # Duplicate conversion check
    dedup_key = f"conversion:{device_id}:{offer_id}"
    if cache.get(dedup_key):
        score += 90; signals.append("duplicate_conversion")
    else:
        cache.set(dedup_key, True, 86400)

    # Check conversion velocity from same IP
    ip_key = f"conv_ip:{ip}"
    count = cache.get(ip_key, 0) + 1
    cache.set(ip_key, count, 3600)
    if count > 5:
        score += 60; signals.append(f"too_many_conversions_same_ip:{count}")

    # Install hijacking: conversion too fast after click
    click_time = context.get("click_time_ms")
    conv_time  = context.get("conversion_time_ms")
    if click_time and conv_time:
        diff_sec = (conv_time - click_time) / 1000
        if diff_sec < 3:
            score += 70; signals.append(f"too_fast_conversion:{diff_sec:.1f}s")

    # VPN/Proxy check
    if context.get("is_vpn"):
        score += 30; signals.append("vpn_conversion")

    return {
        "is_fraud":     score >= 50,
        "fraud_type":   "install_hijacking" if "too_fast" in str(signals) else "conversion_fraud",
        "score":        min(100, score),
        "signals":      signals,
        "should_block": score >= 80,
    }
