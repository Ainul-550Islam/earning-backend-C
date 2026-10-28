"""
Management command: detect_fraud
Run fraud detection across recent conversions and flag suspicious users/conversions.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Run fraud detection on recent conversions'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24,
                            help='Look back N hours')
        parser.add_argument('--threshold', type=float, default=0.7,
                            help='Fraud score threshold (0-1)')
        parser.add_argument('--action', choices=['flag', 'reject', 'report'],
                            default='flag',
                            help='Action to take on flagged conversions')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from api.offerwall.models import OfferConversion
        from api.offerwall.utils.FraudDetector import FraudDetector

        since     = timezone.now() - timedelta(hours=options['hours'])
        threshold = options['threshold']
        action    = options['action']
        dry_run   = options['dry_run']

        qs = OfferConversion.objects.filter(
            status='pending',
            converted_at__gte=since,
        ).select_related('user', 'offer')

        total   = qs.count()
        flagged = 0
        self.stdout.write(f'Scanning {total} pending conversions…')

        for conv in qs.iterator(chunk_size=50):
            try:
                detector = FraudDetector(user=conv.user, offer=conv.offer)
                result   = detector.comprehensive_fraud_check()
                score    = result.get('fraud_score', 0.0)
                if score >= threshold:
                    flagged += 1
                    self.stdout.write(
                        f'  ⚠️  FRAUD score={score:.2f} conv={conv.conversion_id} '
                        f'user={conv.user_id}')
                    if not dry_run:
                        if action == 'reject':
                            conv.status = 'rejected'
                            conv.rejection_reason = f'Auto-rejected: fraud score {score:.2f}'
                            conv.save(update_fields=['status', 'rejection_reason'])
                        elif action == 'flag':
                            conv.offer.is_high_risk = True
                            conv.offer.fraud_score   = score
                            conv.offer.save(update_fields=['is_high_risk', 'fraud_score'])
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ Error on {conv.conversion_id}: {exc}'))

        self.stdout.write(self.style.SUCCESS(
            f'Done — scanned={total} flagged={flagged} action={action}'))
