from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.fraud_detection')

class Command(BaseCommand):
    help = 'Run batch fraud detection on recent submissions'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=1, help='Check submissions from last N hours')

    def handle(self, *args, **options):
        from api.promotions.models import TaskSubmission
        from api.promotions.choices import SubmissionStatus
        from api.promotions.ai.fraud_score import AIFraudScorer
        from api.promotions.governance.penalty_manager import PenaltyManager
        from django.utils import timezone
        from datetime import timedelta

        since   = timezone.now() - timedelta(hours=options['hours'])
        subs    = TaskSubmission.objects.filter(submitted_at__gte=since, status=SubmissionStatus.PENDING).select_related('worker')[:500]
        scorer  = AIFraudScorer()
        penalty = PenaltyManager()
        flagged = banned = 0

        for sub in subs:
            try:
                result = scorer.score_submission(sub.id, None, None, [], sub.worker_id, getattr(sub,'ip_address',''))
                if result.action == 'ban':
                    penalty.apply_penalty(sub.worker_id, 'bot_activity')
                    banned += 1
                elif result.action in ('reject', 'flag'):
                    flagged += 1
            except Exception as e:
                logger.error(f'Fraud check failed for sub {sub.id}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Fraud scan: {len(subs)} checked, {flagged} flagged, {banned} banned'))
