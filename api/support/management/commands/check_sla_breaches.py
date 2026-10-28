# api/support/management/commands/check_sla_breaches.py
"""Check and mark SLA breaches."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Check all active tickets for SLA breaches and mark them'

    def handle(self, *args, **options):
        from api.support.services import sla_service
        result = sla_service.check_breaches()
        self.stdout.write(
            self.style.SUCCESS(
                f"SLA check complete: checked={result.get('checked',0)} "
                f"breached={result.get('breached',0)} "
                f"notified={result.get('notified',0)}"
            )
        )