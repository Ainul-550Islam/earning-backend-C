#!/usr/bin/env python
"""scripts/update_webhooks.py — Update webhook endpoints for all networks."""
import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import argparse

def main():
    parser = argparse.ArgumentParser(description="Manage PostbackEngine webhooks")
    parser.add_argument("--list", action="store_true", help="List all registered webhooks")
    parser.add_argument("--test", action="store_true", help="Test all webhook endpoints")
    args = parser.parse_args()

    from api.postback_engine.models import AdNetworkConfig

    if args.list:
        print("\nRegistered Webhooks:")
        for network in AdNetworkConfig.objects.all():
            metadata = getattr(network, "metadata", {}) or {}
            webhooks = metadata.get("webhooks", [])
            if webhooks:
                print(f"\n  {network.network_key}:")
                for wh in webhooks:
                    print(f"    {wh.get("url", "")} events={wh.get("events")}")

    if args.test:
        print("\nTesting Zapier integration...")
        from api.postback_engine.webhook_manager.zapier_integration import zapier_integration
        results = zapier_integration.test_connection()
        for event, success in results.items():
            print(f"  {event}: {'✓' if success else '✗'}")

        print("\nTesting Make.com integration...")
        from api.postback_engine.webhook_manager.make_integration import make_integration
        results = make_integration.test_connection()
        for event, success in results.items():
            print(f"  {event}: {'✓' if success else '✗'}")

if __name__ == "__main__":
    main()
