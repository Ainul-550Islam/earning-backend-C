"""
api/ai_engine/SCRIPTS/generate_predictions.py
===============================================
CLI Script — Batch predictions generate করো।
Churn, LTV, fraud scores সব users এর জন্য।
Cron job হিসেবে schedule করো।
"""

import argparse
import os
import sys
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


PREDICTION_TYPES = ["churn", "ltv", "fraud", "conversion"]


def generate_batch_predictions(prediction_type: str, tenant_id=None,
                                 batch_size: int = 256, limit: int = None):
    """Batch predictions সব users এর জন্য generate করো।"""
    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from api.ai_engine.services import PredictionService, ChurnPredictionService

    User = get_user_model()
    qs   = User.objects.filter(is_active=True)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    if limit:
        qs = qs[:limit]

    total   = qs.count()
    success = 0
    failed  = 0

    print(f"Generating {prediction_type} predictions for {total} users...")

    for i in range(0, total, batch_size):
        batch = qs[i: i + batch_size]
        for user in batch:
            try:
                if prediction_type == "churn":
                    ChurnPredictionService.predict_churn(user, tenant_id)
                else:
                    input_data = {
                        "user_id":          str(user.id),
                        "account_age_days": 30,
                        "days_since_login": 5,
                        "coin_balance":     float(getattr(user, "coin_balance", 0)),
                        "total_earned":     float(getattr(user, "total_earned", 0)),
                    }
                    PredictionService.predict(prediction_type, input_data, user=user, tenant_id=tenant_id)
                success += 1
            except Exception as e:
                logger.error(f"Prediction error for {user.id}: {e}")
                failed += 1

        print(f"  Progress: {min(i + batch_size, total)}/{total}")

    return {"success": success, "failed": failed, "total": total}


def main():
    parser = argparse.ArgumentParser(description="Generate Batch AI Predictions")
    parser.add_argument("--type",       required=True, choices=PREDICTION_TYPES, help="Prediction type")
    parser.add_argument("--tenant-id",  help="Tenant ID (optional)")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--limit",      type=int, help="Max users to process")
    args = parser.parse_args()

    result = generate_batch_predictions(
        prediction_type=args.type,
        tenant_id=args.tenant_id,
        batch_size=args.batch_size,
        limit=args.limit,
    )

    print(f"\n✅ Batch predictions complete [{args.type}]:")
    print(f"   Success: {result['success']}")
    print(f"   Failed:  {result['failed']}")
    print(f"   Total:   {result['total']}")

    if result["failed"] > result["total"] * 0.20:
        print("⚠️  High failure rate (>20%) — check model deployment status")
        sys.exit(1)


if __name__ == "__main__":
    main()
