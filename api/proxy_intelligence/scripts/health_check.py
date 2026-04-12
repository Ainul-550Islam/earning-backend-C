#!/usr/bin/env python3
"""Script: Health Check — validates the proxy intelligence module deployment."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

def check(name, func):
    try:
        ok, detail = func()
        icon = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"
        print(f"  {icon} [{status}] {name}: {detail}")
        return ok
    except Exception as e:
        print(f"  ✗ [ERROR] {name}: {e}")
        return False

def run():
    print("\n=== Proxy Intelligence Health Check ===\n")
    results = []

    results.append(check("Database: IPIntelligence", lambda: (
        True, f"{__import__('api.proxy_intelligence.models', fromlist=['IPIntelligence']).IPIntelligence.objects.count()} records"
    )))

    results.append(check("Database: Blacklist", lambda: (
        True, f"{__import__('api.proxy_intelligence.models', fromlist=['IPBlacklist']).IPBlacklist.objects.filter(is_active=True).count()} active entries"
    )))

    results.append(check("Cache (Redis)", lambda: (
        lambda c: (c.set("pi:hc", "ok", 5) is True or c.get("pi:hc") == "ok", "Connected")
    )(__import__("django.core.cache", fromlist=["cache"]).cache)))

    results.append(check("Tor Exit Nodes", lambda: (
        True, f"{__import__('api.proxy_intelligence.models', fromlist=['TorExitNode']).TorExitNode.objects.filter(is_active=True).count()} active"
    )))

    results.append(check("ML Models", lambda: (
        True, f"{__import__('api.proxy_intelligence.models', fromlist=['MLModelMetadata']).MLModelMetadata.objects.filter(is_active=True).count()} active models"
    )))

    results.append(check("Integration Credentials", lambda: (
        True, f"{__import__('api.proxy_intelligence.models', fromlist=['IntegrationCredential']).IntegrationCredential.objects.filter(is_active=True).count()} configured"
    )))

    results.append(check("Threat Feeds", lambda: (
        True, f"{__import__('api.proxy_intelligence.models', fromlist=['ThreatFeedProvider']).ThreatFeedProvider.objects.filter(is_active=True).count()} active feeds"
    )))

    passed = sum(results)
    total = len(results)
    print(f"\n{'✓' if passed==total else '!'} {passed}/{total} checks passed.")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    run()
