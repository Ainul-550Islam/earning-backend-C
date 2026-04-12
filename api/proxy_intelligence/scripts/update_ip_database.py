#!/usr/bin/env python3
"""Script: Update IP Database — syncs datacenter ranges from public sources."""
import os, sys, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from api.proxy_intelligence.models import DatacenterIPRange
from django.utils import timezone

SOURCES = [
    {
        "name": "AWS",
        "url": "https://ip-ranges.amazonaws.com/ip-ranges.json",
        "asn": "AS16509",
        "parser": lambda data: [p["ip_prefix"] for p in data.get("prefixes", []) if "ip_prefix" in p],
    },
    {
        "name": "Cloudflare",
        "url": "https://www.cloudflare.com/ips-v4",
        "asn": "AS13335",
        "parser": lambda data: [line.strip() for line in data.split("\n") if line.strip()],
        "raw_text": True,
    },
]

def update():
    total = 0
    for source in SOURCES:
        try:
            resp = requests.get(source["url"], timeout=20)
            resp.raise_for_status()
            ranges = source["parser"](resp.text if source.get("raw_text") else resp.json())
            for cidr in ranges:
                if not cidr: continue
                DatacenterIPRange.objects.update_or_create(
                    cidr=cidr,
                    defaults={
                        "provider_name": source["name"],
                        "asn": source["asn"],
                        "is_active": True,
                        "last_updated": timezone.now(),
                    }
                )
                total += 1
            print(f"  ✓ {source['name']}: {len(ranges)} ranges updated")
        except Exception as e:
            print(f"  ✗ {source['name']}: {e}")
    print(f"\nTotal: {total} IP ranges updated")

if __name__ == "__main__":
    update()
