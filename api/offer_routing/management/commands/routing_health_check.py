"""
Management command: routing_health_check
Usage: python manage.py routing_health_check [--json]

Runs a comprehensive health check across all offer routing services
and prints a coloured report to stdout.
"""

import sys
import json as _json
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run a full health check across all offer routing services."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON instead of human-readable text.",
        )
        parser.add_argument(
            "--fail-on-error",
            action="store_true",
            dest="fail_on_error",
            help="Exit with code 1 if any service reports an error.",
        )

    def handle(self, *args, **options):
        results = {}

        services = {
            "cache": ("offer_routing.services.cache", "cache_service"),
            "ab_test": ("offer_routing.services.ab_test", "ab_test_service"),
            "fallback": ("offer_routing.services.fallback", "fallback_service"),
            "cap": ("offer_routing.services.cap", "cap_service"),
            "targeting": ("offer_routing.services.targeting", "targeting_service"),
            "personalization": ("offer_routing.services.personalization", "personalization_service"),
        }

        for svc_name, (module_path, attr) in services.items():
            try:
                import importlib
                mod = importlib.import_module(module_path)
                svc = getattr(mod, attr, None)
                if svc and hasattr(svc, "health_check"):
                    results[svc_name] = svc.health_check()
                else:
                    results[svc_name] = {"status": "unknown", "error": "no health_check method"}
            except Exception as e:
                results[svc_name] = {"status": "error", "error": str(e)}

        if options["json"]:
            self.stdout.write(_json.dumps(results, indent=2))
        else:
            for svc, info in results.items():
                status = info.get("status", "unknown")
                colour = self.style.SUCCESS if status == "healthy" else self.style.ERROR
                self.stdout.write(colour(f"[{status.upper():^10}] {svc}"))
                if status != "healthy":
                    self.stdout.write(f"           → {info.get('error', info)}")

        unhealthy = [k for k, v in results.items() if v.get("status") not in ("healthy", "ok")]
        if unhealthy and options["fail_on_error"]:
            self.stderr.write(self.style.ERROR(
                f"\n{len(unhealthy)} service(s) unhealthy: {', '.join(unhealthy)}"
            ))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS("\nHealth check complete."))
