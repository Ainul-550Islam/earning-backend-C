"""
Management Command: train_ml_models
Usage: python manage.py train_ml_models [--model-type <type>] [--days <n>] [--activate]
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train ML fraud detection models from historical database data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-type',
            choices=['risk_scoring', 'anomaly_detection', 'vpn_detection',
                     'bot_detection', 'fraud_classification'],
            default='risk_scoring',
            help='Model type to train (default: risk_scoring)'
        )
        parser.add_argument(
            '--save-path', default='/tmp/pi_model.pkl',
            help='Path to save the trained model file'
        )
        parser.add_argument(
            '--days', type=int, default=90,
            help='Days of historical data to use for training (default: 90)'
        )
        parser.add_argument(
            '--activate', action='store_true',
            help='Automatically activate this model after training'
        )
        parser.add_argument(
            '--list-models', action='store_true',
            help='List all registered ML models and exit'
        )

    def handle(self, *args, **options):
        # ── List models mode ───────────────────────────────────────────────
        if options['list_models']:
            from api.proxy_intelligence.models import MLModelMetadata
            models = MLModelMetadata.objects.all().order_by('-trained_at')
            if not models.exists():
                self.stdout.write('No ML models registered.')
                return
            self.stdout.write(f'\n{"Name":<35} {"Version":<15} {"Type":<25} {"Active":<8} {"AUC":<8} {"F1":<8}')
            self.stdout.write('-' * 100)
            for m in models:
                active_str = '✓' if m.is_active else ' '
                self.stdout.write(
                    f'{m.name:<35} {m.version:<15} {m.model_type:<25} '
                    f'{active_str:<8} {str(m.auc_roc or "N/A"):<8} {str(m.f1_score or "N/A"):<8}'
                )
            return

        # ── Training mode ──────────────────────────────────────────────────
        model_type = options['model_type']
        save_path  = options['save_path']
        days       = options['days']

        self.stdout.write(self.style.NOTICE(
            f'\n[{timezone.now().strftime("%Y-%m-%d %H:%M")}] '
            f'Training {model_type} model from last {days} days of data...'
        ))
        self.stdout.write(f'  Save path:  {save_path}')
        self.stdout.write(f'  Auto-activate: {options["activate"]}')
        self.stdout.write('')

        try:
            from api.proxy_intelligence.ai_ml_engines.model_trainer import ModelTrainer
            trainer = ModelTrainer(model_type=model_type)

            # Show training data size
            X, y = trainer.prepare_training_data(days=days)
            positives = sum(y)
            negatives = len(y) - positives
            self.stdout.write(f'  Training samples: {len(X)}')
            self.stdout.write(f'  Positive (fraud): {positives} ({round(positives/max(len(y),1)*100,1)}%)')
            self.stdout.write(f'  Negative (clean): {negatives}')
            self.stdout.write('')

            if len(X) < 50:
                self.stdout.write(self.style.WARNING(
                    f'⚠️  Insufficient data ({len(X)} samples). Need ≥50 labeled fraud attempts.'
                    f' Run the system longer or import historical data.'
                ))
                return

            results = trainer.train_and_register(save_path=save_path)

            if 'error' in results:
                self.stdout.write(self.style.ERROR(f'✗ Training failed: {results["error"]}'))
                return

            # Success output
            self.stdout.write(self.style.SUCCESS('✓ Model trained successfully'))
            self.stdout.write(f'  Model ID:      {results.get("model_id", "N/A")}')
            self.stdout.write(f'  Version:       {results.get("version", "N/A")}')
            self.stdout.write(f'  AUC-ROC:       {results.get("auc_roc", "N/A")}')
            self.stdout.write(f'  F1 Score:      {results.get("f1_score", "N/A")}')
            self.stdout.write(f'  Precision:     {results.get("precision", "N/A")}')
            self.stdout.write(f'  Recall:        {results.get("recall", "N/A")}')
            self.stdout.write(f'  Accuracy:      {results.get("accuracy", "N/A")}')

            # Auto-activate if requested
            if options['activate'] and results.get('model_id'):
                from api.proxy_intelligence.models import MLModelMetadata
                MLModelMetadata.objects.filter(model_type=model_type).update(is_active=False)
                MLModelMetadata.objects.filter(pk=results['model_id']).update(is_active=True)
                self.stdout.write(self.style.SUCCESS(
                    f'\n✓ Model {results.get("version")} activated for {model_type}'
                ))
            else:
                self.stdout.write(
                    f'\n  To activate: python manage.py train_ml_models --activate'
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Training failed with exception: {e}'))
            logger.exception(f'ML model training failed: {e}')
            raise
