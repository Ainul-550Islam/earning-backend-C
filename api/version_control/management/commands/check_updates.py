# =============================================================================
# version_control/management/commands/check_updates.py
# =============================================================================
"""
Management command: check_updates

Checks whether a given platform + version requires an update according to
the currently active policies.

Examples::

    python manage.py check_updates --platform ios --version 1.5.0
    python manage.py check_updates --platform android --version 2.0.0
    python manage.py check_updates --all-platforms --version 1.5.0
"""

from __future__ import annotations

import json
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check whether a platform/version requires an update."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--platform",
            type=str,
            default=None,
            help="Platform identifier (ios, android, web, ...).",
        )
        parser.add_argument(
            "--version",
            type=str,
            required=True,
            help="Client version string in semver format.",
        )
        parser.add_argument(
            "--all-platforms",
            action="store_true",
            default=False,
            dest="all_platforms",
            help="Run check for all known platforms.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            default=False,
            dest="output_json",
            help="Output result as JSON.",
        )

    def handle(self, *args, **options) -> None:
        from version_control.services import VersionCheckService
        from version_control.constants import ALL_PLATFORMS

        version      = options["version"]
        all_platforms = options["all_platforms"]
        output_json  = options["output_json"]
        platform     = options.get("platform")

        if not all_platforms and not platform:
            raise CommandError("Provide --platform or --all-platforms.")

        platforms = list(ALL_PLATFORMS) if all_platforms else [platform]
        results   = {}

        for p in platforms:
            try:
                result = VersionCheckService.check(platform=p, client_version=version)
                results[p] = result
            except Exception as exc:
                results[p] = {"error": str(exc)}

        if output_json:
            self.stdout.write(json.dumps(results, indent=2))
            return

        for p, result in results.items():
            if "error" in result:
                self.stderr.write(
                    self.style.ERROR(f"  {p}: ERROR — {result['error']}")
                )
            elif result.get("update_required"):
                self.stdout.write(
                    self.style.WARNING(
                        f"  {p}: UPDATE {result['update_type'].upper()} "
                        f"→ {result['target_version']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"  {p}: OK (no update required)")
                )
