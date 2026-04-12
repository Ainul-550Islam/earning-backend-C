"""
api/ai_engine/SCRIPTS/update_features.py
==========================================
CLI Script — Feature Store আপডেট করো।
সব active users এর behavioral features fresh করো।
Schedule: প্রতি 6 ঘণ্টায়।
"""

import argparse
import os
import sys
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_user_features(tenant_id=None, batch_size: int = 500):
    """সব users এর features update করো।"""
    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from api.ai_engine.ML_MODELS.feature_engineering import FeatureEngineer
    from api.ai_engine.repository import FeatureRepository

    User = get_user_model()
    qs   = User.objects.filter(is_active=True)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    total   = qs.count()
    updated = 0
    errors  = 0

    print(f"Updating features for {total} users...")

    engineer = FeatureEngineer(feature_type="behavioral")

    for i in range(0, total, batch_size):
        batch = qs[i: i + batch_size]
        for user in batch:
            try:
                raw_data = {
                    "user_id":             str(user.id),
                    "account_age_days":    (django.utils.timezone.now() - user.date_joined).days,
                    "days_since_login":    (django.utils.timezone.now() - (user.last_login or user.date_joined)).days,
                    "coin_balance":        float(getattr(user, "coin_balance", 0)),
                    "total_earned":        float(getattr(user, "total_earned", 0)),
                    "country":             getattr(user, "country", "BD"),
                }
                features = engineer.extract(raw_data)
                FeatureRepository.upsert(
                    entity_id=str(user.id),
                    feature_type="behavioral",
                    features=features,
                    entity_type="user",
                    tenant_id=tenant_id,
                )
                updated += 1
            except Exception as e:
                logger.error(f"Feature update error for {user.id}: {e}")
                errors += 1

        print(f"  Progress: {min(i + batch_size, total)}/{total} users processed")

    return {"updated": updated, "errors": errors, "total": total}


def main():
    parser = argparse.ArgumentParser(description="Update AI Feature Store")
    parser.add_argument("--tenant-id", help="Specific tenant ID (optional)")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size")
    args = parser.parse_args()

    result = update_user_features(
        tenant_id=args.tenant_id,
        batch_size=args.batch_size,
    )
    print(f"\n✅ Feature update complete:")
    print(f"   Updated: {result['updated']}")
    print(f"   Errors:  {result['errors']}")
    print(f"   Total:   {result['total']}")

    if result["errors"] > result["total"] * 0.10:
        print("⚠️  High error rate — check logs")
        sys.exit(1)


if __name__ == "__main__":
    main()
