# kyc/management/commands/run_periodic_aml_screening.py  ── WORLD #1
"""
Management command: python manage.py run_periodic_aml_screening
Re-screens all verified KYC holders against updated PEP/sanctions lists.
Run weekly via cron / celery beat.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Re-screen all verified KYC users against PEP/Sanctions lists'

    def add_arguments(self, parser):
        parser.add_argument('--days-since', type=int, default=30, help='Re-screen those not screened in N days')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--provider', default='local', help='local | complyadvantage | refinitiv')

    def handle(self, *args, **options):
        from api.kyc.models import KYC
        from api.kyc.aml.screening_service import AMLScreeningService
        from api.kyc.aml.models import PEPSanctionsScreening

        days_since = options['days_since']
        dry_run    = options['dry_run']
        provider   = options['provider']
        cutoff     = timezone.now() - datetime.timedelta(days=days_since)

        # KYCs not screened recently
        screened_kyc_ids = PEPSanctionsScreening.objects.filter(
            screened_at__gte=cutoff
        ).values_list('kyc_id', flat=True)

        to_screen = KYC.objects.filter(
            status='verified'
        ).exclude(id__in=screened_kyc_ids)

        count = to_screen.count()
        self.stdout.write(f'Found {count} KYCs to re-screen (not screened in {days_since} days)')

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Would screen {count} KYCs'))
            return

        service = AMLScreeningService(provider=provider)
        hits = 0
        for i, kyc in enumerate(to_screen, 1):
            try:
                result = service.screen(kyc)
                service.save_result(kyc, result)
                if result.is_hit:
                    hits += 1
                    self.stdout.write(self.style.WARNING(
                        f'[{i}/{count}] HIT: KYC #{kyc.id} {kyc.full_name} — PEP:{result.is_pep} Sanctioned:{result.is_sanctioned}'
                    ))
            except Exception as e:
                self.stderr.write(f'Error screening KYC #{kyc.id}: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'Screening complete: {count} screened, {hits} hits found'
        ))
