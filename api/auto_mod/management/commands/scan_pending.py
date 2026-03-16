# =============================================================================
# auto_mod/management/commands/scan_pending.py
# =============================================================================

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Process all PENDING suspicious submissions through the AI pipeline."

    def add_arguments(self, parser):
        parser.add_argument("--limit",   type=int, default=100, help="Max submissions to process.")
        parser.add_argument("--type",    dest="submission_type", default=None,
                            help="Filter by submission_type (e.g. task_proof).")
        parser.add_argument("--async",   action="store_true", dest="use_async",
                            help="Dispatch as individual Celery tasks.")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                            help="Show count without processing.")

    def handle(self, *args, **options):
        from auto_mod.models import SuspiciousSubmission
        from auto_mod.tasks import scan_submission
        from auto_mod.services import ModerationService

        qs = SuspiciousSubmission.objects.pending()
        if options["submission_type"]:
            qs = qs.for_type(options["submission_type"])
        qs = qs.order_by("created_at")[: options["limit"]]

        total = qs.count()
        self.stdout.write(f"Found {total} pending submission(s).")

        if options["dry_run"]:
            return

        processed = errors = 0
        for sub in qs:
            try:
                if options["use_async"]:
                    scan_submission.delay(
                        content_type=sub.content_type,
                        content_id=sub.content_id,
                        submission_type=sub.submission_type,
                        user_id=str(sub.submitted_by_id) if sub.submitted_by_id else None,
                    )
                else:
                    ModerationService.process_submission(
                        content_type=sub.content_type,
                        content_id=sub.content_id,
                        submission_type=sub.submission_type,
                        submitted_by=sub.submitted_by,
                    )
                processed += 1
            except Exception as exc:
                self.stderr.write(f"  Error pk={sub.pk}: {exc}")
                errors += 1

        self.stdout.write(
            self.style.SUCCESS(f"Done — processed={processed} errors={errors}")
        )
