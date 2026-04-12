"""
api/ai_engine/SCRIPTS/deploy_model.py
========================================
CLI Script — AI Model production এ deploy করো।
Safety checks → version promote → endpoint activate।
"""

import argparse
import os
import sys
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def deploy_model(model_id: str, version_id: str = None,
                  skip_checks: bool = False) -> dict:
    """Model deploy করো সব safety checks সহ।"""
    import django
    django.setup()

    from api.ai_engine.models import AIModel, ModelVersion
    from api.ai_engine.services import ModelManagementService
    from api.ai_engine.ML_PIPELINES.evaluation_pipeline import EvaluationPipeline

    # Step 1: Model exist check
    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return {"success": False, "error": f"Model not found: {model_id}"}

    print(f"Deploying: {model.name} [{model.algorithm}]")

    # Step 2: Evaluation check
    if not skip_checks:
        print("Running evaluation checks...")
        eval_result = EvaluationPipeline().run(model_id)
        if not eval_result.get("passed", True):
            return {
                "success": False,
                "error":   "Evaluation failed",
                "metrics": eval_result.get("metrics", {}),
            }
        print(f"  ✅ F1={eval_result.get('metrics', {}).get('f1_score', 0):.3f} AUC={eval_result.get('metrics', {}).get('auc_roc', 0):.3f}")

    # Step 3: Version promote if specified
    if version_id:
        from api.ai_engine.repository import ModelVersionRepository
        try:
            version = ModelVersionRepository.promote_to_production(version_id)
            print(f"  ✅ Version {version.version} promoted to production")
        except Exception as e:
            print(f"  ⚠️  Version promotion failed: {e}")

    # Step 4: Deploy
    try:
        deployed_model = ModelManagementService.deploy_model(model_id)
        print(f"  ✅ Model deployed: status={deployed_model.status}")
        return {
            "success":    True,
            "model_name": deployed_model.name,
            "status":     deployed_model.status,
            "model_id":   model_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Deploy AI Model to Production")
    parser.add_argument("--model-id",   required=True, help="AIModel UUID")
    parser.add_argument("--version-id", help="Specific ModelVersion UUID to promote")
    parser.add_argument("--skip-checks", action="store_true", help="Skip evaluation checks")
    args = parser.parse_args()

    print(f"\n🚀 Starting deployment: model={args.model_id}")
    result = deploy_model(args.model_id, args.version_id, args.skip_checks)

    if result["success"]:
        print(f"\n✅ Deployment successful!")
        print(f"   Model: {result.get('model_name')}")
        print(f"   Status: {result.get('status')}")
    else:
        print(f"\n❌ Deployment failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
