"""
api/ai_engine/SCRIPTS/train_model.py
=====================================
CLI script — model training চালাও।
Usage: python -m api.ai_engine.SCRIPTS.train_model --model-id <id> --dataset <path>
"""

import argparse
import logging
import os
import sys

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Train AI Model')
    parser.add_argument('--model-id',  required=True, help='AIModel UUID')
    parser.add_argument('--dataset',   required=True, help='Dataset path')
    parser.add_argument('--n-estimators', type=int, default=100)
    parser.add_argument('--max-depth',    type=int, default=6)
    args = parser.parse_args()

    import django
    django.setup()

    from api.ai_engine.services import TrainingService
    hyperparams = {
        'n_estimators': args.n_estimators,
        'max_depth':    args.max_depth,
    }

    print(f"Starting training: model={args.model_id} dataset={args.dataset}")
    try:
        job = TrainingService.start_training(args.model_id, args.dataset, hyperparams)
        print(f"✅ Training started: job_id={job.job_id}")
    except Exception as e:
        print(f"❌ Training failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
