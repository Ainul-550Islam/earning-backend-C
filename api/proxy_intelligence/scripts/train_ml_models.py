#!/usr/bin/env python3
"""
Script: train_ml_models.py
============================
Standalone script to train proxy intelligence ML models
from historical database data.

Usage:
    python scripts/train_ml_models.py
    python scripts/train_ml_models.py --model-type risk_scoring --days 90
    python scripts/train_ml_models.py --model-type anomaly_detection --activate
    python scripts/train_ml_models.py --list-models
    python scripts/train_ml_models.py --activate-model <model_id>

Requires Django to be configured and scikit-learn to be installed.
    pip install scikit-learn joblib
"""
import os
import sys
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s'
)

from django.utils import timezone

MODEL_TYPES = [
    'risk_scoring',
    'anomaly_detection',
    'vpn_detection',
    'fraud_classification',
]


def list_models():
    """List all registered ML models."""
    from api.proxy_intelligence.models import MLModelMetadata

    models = MLModelMetadata.objects.all().order_by('-trained_at')
    if not models.exists():
        print('  No ML models registered yet.')
        return

    print(f'\n  {"ID":<36} {"Name":<35} {"Type":<25} {"Active":<8} {"AUC":>8} {"F1":>8}')
    print(f'  {"-"*125}')
    for m in models:
        active_str = '✓ YES' if m.is_active else 'no'
        print(
            f'  {str(m.pk):<36} '
            f'{m.name[:34]:<35} '
            f'{m.model_type:<25} '
            f'{active_str:<8} '
            f'{str(round(m.auc_roc, 4) if m.auc_roc else "N/A"):>8} '
            f'{str(round(m.f1_score, 4) if m.f1_score else "N/A"):>8}'
        )


def activate_model(model_id: str):
    """Activate a specific model by ID."""
    from api.proxy_intelligence.models import MLModelMetadata
    try:
        model = MLModelMetadata.objects.get(pk=model_id)
        # Deactivate all models of same type
        MLModelMetadata.objects.filter(
            model_type=model.model_type
        ).update(is_active=False)
        # Activate this one
        model.is_active = True
        model.save(update_fields=['is_active'])
        print(f'  ✓ Activated: {model.name} v{model.version} ({model.model_type})')
    except MLModelMetadata.DoesNotExist:
        print(f'  ✗ Model not found: {model_id}')
    except Exception as e:
        print(f'  ✗ Error: {e}')


def train_supervised(model_type: str, days: int, save_path: str,
                      activate: bool = False):
    """Train a supervised fraud classification model."""
    from api.proxy_intelligence.ai_ml_engines.model_trainer import ModelTrainer

    print(f'\n  Training supervised model: {model_type}')
    print(f'  Using last {days} days of data...')
    print(f'  Save path: {save_path}')
    print('')

    trainer = ModelTrainer(model_type=model_type)

    # Show training data info
    X, y = trainer.prepare_training_data(days=days)
    pos = sum(y)
    neg = len(y) - pos
    print(f'  Training samples:  {len(X):,}')
    print(f'  Positive (fraud):  {pos:,} ({round(pos/max(len(y),1)*100,1)}%)')
    print(f'  Negative (clean):  {neg:,}')
    print('')

    if len(X) < 50:
        print(f'  ✗ Insufficient data ({len(X)} samples). Need ≥50 labeled fraud attempts.')
        print('    Run the platform longer, or import historical fraud data.')
        return

    # Train
    print('  Training model...', end='', flush=True)
    results = trainer.train_and_register(save_path=save_path)
    print(' done')

    if 'error' in results:
        print(f'  ✗ Training failed: {results["error"]}')
        return

    # Results
    print(f'\n  ✓ Model trained successfully!')
    print(f'    Model ID:    {results.get("model_id", "N/A")}')
    print(f'    Version:     {results.get("version", "N/A")}')
    print(f'    AUC-ROC:     {results.get("auc_roc", "N/A")}')
    print(f'    F1 Score:    {results.get("f1_score", "N/A")}')
    print(f'    Precision:   {results.get("precision", "N/A")}')
    print(f'    Recall:      {results.get("recall", "N/A")}')
    print(f'    Accuracy:    {results.get("accuracy", "N/A")}')
    print(f'    Saved to:    {save_path}')

    if activate and results.get('model_id'):
        activate_model(results['model_id'])


def train_anomaly(days: int, save_path: str, activate: bool = False):
    """Train an unsupervised anomaly detection model."""
    from api.proxy_intelligence.ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector

    print(f'\n  Training unsupervised anomaly detector (IsolationForest)...')
    print(f'  Using last {days} days of clean IP data as normal baseline...')

    detector = UnsupervisedAnomalyDetector(algorithm='isolation_forest', contamination=0.05)
    metrics  = detector.fit_from_db(days=days)

    if 'error' in metrics:
        print(f'  ✗ Training failed: {metrics["error"]}')
        return

    print(f'  ✓ Anomaly detector trained!')
    print(f'    Training samples: {metrics.get("training_samples", "N/A"):,}')
    print(f'    Anomaly rate:     {metrics.get("anomaly_rate", 0):.1%}')
    print(f'    Mean score:       {round(metrics.get("mean_score", 0), 4)}')

    saved = detector.save(save_path)
    if saved:
        print(f'    Saved to:         {save_path}')
        model_id = detector.register_in_db(save_path, metrics)
        if model_id:
            print(f'    Model ID:         {model_id}')
            if activate:
                activate_model(model_id)


def main():
    parser = argparse.ArgumentParser(
        description='Proxy Intelligence ML Model Trainer'
    )
    parser.add_argument('--model-type',
                        choices=MODEL_TYPES, default='risk_scoring',
                        help='Model type to train (default: risk_scoring)')
    parser.add_argument('--days', type=int, default=90,
                        help='Days of historical data to use (default: 90)')
    parser.add_argument('--save-path', default='/tmp/pi_model.pkl',
                        help='Path to save the trained model (default: /tmp/pi_model.pkl)')
    parser.add_argument('--activate', action='store_true',
                        help='Automatically activate this model after training')
    parser.add_argument('--list-models', action='store_true',
                        help='List all registered models and exit')
    parser.add_argument('--activate-model', type=str, default=None,
                        help='Activate a specific model by UUID')
    parser.add_argument('--anomaly', action='store_true',
                        help='Train unsupervised anomaly detector instead')

    args = parser.parse_args()

    print(f'\n[{timezone.now().strftime("%Y-%m-%d %H:%M")}] '
          f'Proxy Intelligence ML Trainer')
    print('='*55)

    if args.list_models:
        list_models()
        return

    if args.activate_model:
        activate_model(args.activate_model)
        return

    try:
        import sklearn
        print(f'  scikit-learn version: {sklearn.__version__}')
    except ImportError:
        print('  ✗ scikit-learn not installed. Run: pip install scikit-learn joblib')
        sys.exit(1)

    if args.anomaly or args.model_type == 'anomaly_detection':
        train_anomaly(args.days, args.save_path, args.activate)
    else:
        train_supervised(args.model_type, args.days, args.save_path, args.activate)

    print('\nDone.')


if __name__ == '__main__':
    main()
