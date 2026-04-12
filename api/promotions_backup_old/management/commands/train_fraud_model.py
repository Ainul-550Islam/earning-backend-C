from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.train_fraud')

class Command(BaseCommand):
    help = 'Train/retrain fraud prediction ML model on recent data'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Training data window')

    def handle(self, *args, **options):
        from api.promotions.data_science.fraud_prediction import FraudPredictor
        predictor = FraudPredictor()
        result    = predictor.train_model(days=options['days'])
        self.stdout.write(self.style.SUCCESS(
            f"Model trained: accuracy={result.get('accuracy',0):.3f} "
            f"f1={result.get('f1',0):.3f} samples={result.get('samples',0)}"
        ))
