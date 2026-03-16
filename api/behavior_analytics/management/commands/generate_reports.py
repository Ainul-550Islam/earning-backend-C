# =============================================================================
# behavior_analytics/management/commands/generate_reports.py
# =============================================================================
"""
Management command: generate_reports

Generates daily or weekly analytics reports on demand.

Examples::

    # Generate yesterday's daily report
    python manage.py generate_reports --type daily

    # Generate daily report for a specific date
    python manage.py generate_reports --type daily --date 2024-03-15

    # Generate weekly report (previous week)
    python manage.py generate_reports --type weekly

    # Generate weekly report for a specific week start
    python manage.py generate_reports --type weekly --week-start 2024-03-11

    # Dispatch to Celery instead of running inline
    python manage.py generate_reports --type daily --async
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate daily or weekly analytics reports."

    REPORT_TYPES = ("daily", "weekly")

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--type",
            choices=self.REPORT_TYPES,
            required=True,
            dest="report_type",
            help="Type of report to generate.",
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Target date for daily report (YYYY-MM-DD). Default: yesterday.",
        )
        parser.add_argument(
            "--week-start",
            type=str,
            default=None,
            dest="week_start",
            help="Week start (Monday, YYYY-MM-DD) for weekly report.",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            default=False,
            dest="use_async",
            help="Dispatch to Celery instead of running inline.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Optional file path to write the report JSON.",
        )

    def handle(self, *args, **options) -> None:
        report_type = options["report_type"]
        use_async   = options["use_async"]
        output_path = options.get("output")

        self.stdout.write(
            self.style.NOTICE(
                f"generate_reports: type={report_type} async={use_async}"
            )
        )

        if use_async:
            self._dispatch_async(report_type, options)
            return

        report = self._generate_inline(report_type, options)

        if output_path:
            try:
                with open(output_path, "w", encoding="utf-8") as fh:
                    json.dump(report, fh, indent=2, default=str)
                self.stdout.write(
                    self.style.SUCCESS(f"Report written to: {output_path}")
                )
            except OSError as exc:
                raise CommandError(f"Cannot write to '{output_path}': {exc}") from exc
        else:
            self.stdout.write(json.dumps(report, indent=2, default=str))

        self.stdout.write(self.style.SUCCESS("Done."))

    # ------------------------------------------------------------------

    def _generate_inline(self, report_type: str, options: dict) -> dict:
        if report_type == "daily":
            from behavior_analytics.reports.daily_report import DailyReportGenerator
            raw_date = options.get("date")
            target   = self._parse_date(raw_date) if raw_date else None
            return DailyReportGenerator().generate(target_date=target)

        if report_type == "weekly":
            from behavior_analytics.reports.weekly_analytics import WeeklyReportGenerator
            raw_week = options.get("week_start")
            week_start = self._parse_date(raw_week) if raw_week else None
            return WeeklyReportGenerator().generate(week_start=week_start)

        raise CommandError(f"Unknown report type: {report_type}")

    def _dispatch_async(self, report_type: str, options: dict) -> None:
        if report_type == "daily":
            from behavior_analytics.tasks import generate_daily_report
            raw = options.get("date")
            generate_daily_report.delay(raw)
            self.stdout.write(f"  → Daily report task queued (date={raw or 'yesterday'}).")

        elif report_type == "weekly":
            from behavior_analytics.tasks import generate_weekly_report
            raw = options.get("week_start")
            generate_weekly_report.delay(raw)
            self.stdout.write(f"  → Weekly report task queued (week_start={raw or 'auto'}).")

    @staticmethod
    def _parse_date(raw: str) -> date:
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError(
                f"Invalid date format '{raw}'. Use YYYY-MM-DD."
            ) from exc
