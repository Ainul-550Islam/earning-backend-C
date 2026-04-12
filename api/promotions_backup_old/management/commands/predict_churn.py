from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.churn')

class Command(BaseCommand):
    help = 'Predict users likely to churn and trigger retention campaigns'

    def add_arguments(self, parser):
        parser.add_argument('--threshold', type=float, default=0.7, help='Churn probability threshold')

    def handle(self, *args, **options):
        from api.promotions.data_science.churn_prediction import ChurnPredictor
        from api.promotions.services.notification_service import NotificationService
        predictor  = ChurnPredictor()
        at_risk    = predictor.get_at_risk_users(threshold=options['threshold'])
        notifier   = NotificationService()
        sent = 0

        for user_id, prob in at_risk[:500]:
            try:
                notifier.send(user_id, 'retention_offer', {'churn_probability': prob})
                sent += 1
            except Exception: pass

        self.stdout.write(self.style.SUCCESS(
            f"Churn prediction: {len(at_risk)} at-risk users, {sent} retention messages sent"
        ))
