"""
Management command: recalculate_scores
Usage: python manage.py recalculate_scores [--tenant-id N] [--dry-run]

Recalculates offer quality and routing scores for all active offers.
"""

import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Recalculate offer quality and routing scores."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", dest="tenant_id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                            help="Show what would be recalculated without writing.")

    def handle(self, *args, **options):
        from offer_routing.services.domain import OfferQualityService

        svc = OfferQualityService()
        tenant_id = options.get("tenant_id")

        qs = User.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(id=tenant_id)

        for tenant in qs:
            if options["dry_run"]:
                report = svc.get_quality_report(tenant_id=tenant.id)
                self.stdout.write(
                    f"[DRY RUN] Tenant {tenant.id}: would recalculate "
                    f"{report.get('total_offers', 0)} offers"
                )
            else:
                result = svc.recalculate_all_scores(tenant_id=tenant.id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Tenant {tenant.id}: {result.get('recalculated_count', 0)} scores updated"
                    )
                )

        self.stdout.write(self.style.SUCCESS("\nScore recalculation complete."))
