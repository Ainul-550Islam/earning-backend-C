#!/usr/bin/env python
"""scripts/sync_networks.py — Sync/validate network configurations."""
import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

def main():
    from api.postback_engine.models import AdNetworkConfig
    from api.postback_engine.network_adapters.adapters import ADAPTER_REGISTRY
    from api.postback_engine.security.ip_whitelist import ip_whitelist_manager

    networks = AdNetworkConfig.objects.all()
    print(f"\nNetwork Sync Report — {networks.count()} networks")
    print("=" * 60)

    for network in networks:
        issues = []
        if not network.secret_key:
            issues.append("No secret_key (signature verification disabled)")
        if not network.ip_whitelist:
            issues.append("No IP whitelist (all IPs allowed)")
        if network.network_key not in ADAPTER_REGISTRY:
            issues.append(f"No adapter registered for '{network.network_key}'")

        # Validate IP whitelist format
        if network.ip_whitelist:
            is_valid, errors = ip_whitelist_manager.validate_entries(network.ip_whitelist)
            if not is_valid:
                issues.extend([f"Whitelist: {e}" for e in errors])

        # Invalidate cache to ensure fresh config
        from api.postback_engine.security.ip_whitelist import ip_whitelist_manager
        ip_whitelist_manager.invalidate_cache(network)

        status = "✓" if not issues else "⚠"
        print(f"  {status} {network.network_key:20s} | active={network.is_active} | issues={len(issues)}")
        for issue in issues:
            print(f"     → {issue}")

    print("\nSync complete.")

if __name__ == "__main__":
    main()
