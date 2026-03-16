from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.process_pending')

class Command(BaseCommand):
    help = 'Auto-review pending submissions older than 24h using AI'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='Process submissions older than N hours')
        parser.add_argument('--limit', type=int, default=100, help='Max submissions to process')

    def handle(self, *args, **options):
        from api.promotions.models import TaskSubmission
        from api.promotions.choices import SubmissionStatus
        from api.promotions.services.task_service import TaskService
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=options['hours'])
        pending = TaskSubmission.objects.filter(
            status=SubmissionStatus.PENDING,
            submitted_at__lte=cutoff
        ).values_list('id', flat=True)[:options['limit']]

        service   = TaskService()
        approved  = rejected = escalated = 0

        for sub_id in pending:
            result = service.auto_review(sub_id)
            if result.get('status') == 'approved':     approved  += 1
            elif result.get('status') == 'rejected':   rejected  += 1
            else:                                       escalated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Processed {approved+rejected+escalated} submissions: '
            f'approved={approved} rejected={rejected} escalated={escalated}'
        ))
