# =============================================================================
# version_control/management/commands/maintenance_mode.py
# =============================================================================
"""
Management command: maintenance_mode

Enable or disable maintenance mode from the command line (useful in
deploy scripts and Ansible playbooks).

Examples::

    # Enable immediately for 30 minutes (all platforms)
    python manage.py maintenance_mode --enable --duration 30 --title "Deploy v2"

    # Enable for iOS and Android only
    python manage.py maintenance_mode --enable --platforms ios android --duration 45

    # Disable the currently active window
    python manage.py maintenance_mode --disable

    # Show current status
    python manage.py maintenance_mode --status
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Enable or disable maintenance mode."

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--enable",
            action="store_true",
            dest="enable",
            help="Enable maintenance mode.",
        )
        group.add_argument(
            "--disable",
            action="store_true",
            dest="disable",
            help="Disable the currently active maintenance window.",
        )
        group.add_argument(
            "--status",
            action="store_true",
            dest="status",
            help="Show current maintenance status.",
        )

        parser.add_argument(
            "--title",
            type=str,
            default="Scheduled Maintenance",
            help="Title for the maintenance window (--enable only).",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="",
            help="User-visible description.",
        )
        parser.add_argument(
            "--duration",
            type=int,
            default=60,
            help="Duration in minutes (--enable only). Default: 60.",
        )
        parser.add_argument(
            "--platforms",
            nargs="*",
            default=[],
            help="Restrict to specific platforms. Default: all.",
        )

    def handle(self, *args, **options) -> None:
        if options["status"]:
            self._show_status()
        elif options["enable"]:
            self._enable(options)
        elif options["disable"]:
            self._disable()

    # ------------------------------------------------------------------

    def _show_status(self) -> None:
        from version_control.models import MaintenanceSchedule
        active = MaintenanceSchedule.objects.currently_active().first()
        if active:
            self.stdout.write(
                self.style.WARNING(
                    f"Maintenance ACTIVE: '{active.title}'\n"
                    f"  Scheduled end: {active.scheduled_end}\n"
                    f"  Platforms: {active.platforms or 'ALL'}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Maintenance: INACTIVE"))

    def _enable(self, options: dict) -> None:
        from datetime import timedelta
        from version_control.services import MaintenanceService

        duration   = options["duration"]
        title      = options["title"]
        description = options["description"]
        platforms  = options["platforms"]

        now   = timezone.now()
        start = now
        end   = now + timedelta(minutes=duration)

        self.stdout.write(
            f"Enabling maintenance mode: '{title}' "
            f"for {duration} min on platforms={platforms or 'ALL'}"
        )

        try:
            schedule = MaintenanceService.create_schedule(
                title=title,
                description=description,
                scheduled_start=start,
                scheduled_end=end,
                platforms=platforms,
                notify_users=False,
            )
            MaintenanceService.start_maintenance(schedule)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Maintenance mode ENABLED. Schedule ID: {schedule.pk}"
                )
            )
        except Exception as exc:
            raise CommandError(f"Failed to enable maintenance mode: {exc}") from exc

    def _disable(self) -> None:
        from version_control.models import MaintenanceSchedule
        from version_control.services import MaintenanceService

        schedule = MaintenanceSchedule.objects.currently_active().first()
        if not schedule:
            self.stdout.write(self.style.NOTICE("No active maintenance window found."))
            return

        try:
            MaintenanceService.end_maintenance(schedule)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Maintenance mode DISABLED. Schedule: {schedule.pk}"
                )
            )
        except Exception as exc:
            raise CommandError(f"Failed to disable maintenance mode: {exc}") from exc
