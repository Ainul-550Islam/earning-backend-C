"""
api/ai_engine/SCRIPTS/retrain_model.py
=========================================
CLI Script — Model retraining management।
Drift check, auto-retrain, version promotion।
CI/CD pipeline ও scheduled jobs এর জন্য।
"""

import argparse
import os
import sys
import json
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_retrain_needed(model_id: str) -> dict:
    import django; django.setup()
    from api.ai_engine.ML_PIPELINES.retraining_pipeline import RetrainingPipeline
    from api.ai_engine.repository import DriftRepository

    pipeline     = RetrainingPipeline()
    needs_retrain = pipeline.should_retrain(model_id)
    drift_log    = DriftRepository.get_latest(model_id)

    return {
        'model_id':       model_id,
        'needs_retrain':  needs_retrain,
        'drift_status':   drift_log.status if drift_log else 'unknown',
        'drift_score':    float(drift_log.drift_score) if drift_log else 0.0,
        'psi_score':      float(drift_log.psi_score) if drift_log else 0.0,
        'retrain_reason': (
            'Critical data drift detected' if drift_log and drift_log.status == 'critical' else
            'Model age > 30 days'          if needs_retrain else
            'No retraining needed'
        ),
    }


def retrain_model(model_id: str, dataset_path: str = 'auto',
                  force: bool = False, async_mode: bool = False) -> dict:
    import django; django.setup()
    from api.ai_engine.models import AIModel

    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return {'success': False, 'error': f'Model not found: {model_id}'}

    print(f"📊 Model: {model.name} [{model.algorithm}]")

    if not force:
        check = check_retrain_needed(model_id)
        if not check['needs_retrain']:
            print(f"✅ {check['retrain_reason']} — skipping")
            return {'success': True, 'skipped': True, 'reason': check['retrain_reason']}
        print(f"⚠️  Retrain needed: {check['retrain_reason']}")

    if async_mode:
        try:
            from api.ai_engine.tasks import task_train_model
            task = task_train_model.delay(model_id, dataset_path)
            return {'success': True, 'async': True, 'task_id': str(task.id)}
        except Exception as e:
            logger.warning(f"Celery unavailable: {e} — running sync")

    # Synchronous training
    from api.ai_engine.ML_PIPELINES.retraining_pipeline import RetrainingPipeline
    result = RetrainingPipeline().run(model_id, dataset_path)
    return {'success': result.get('status') == 'completed', **result}


def retrain_all_due(tenant_id: str = None, dry_run: bool = False) -> list:
    import django; django.setup()
    from api.ai_engine.models import AIModel

    qs = AIModel.objects.filter(status='deployed', is_active=True)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    results = []
    for model in qs:
        check = check_retrain_needed(str(model.id))
        if check['needs_retrain']:
            if dry_run:
                results.append({
                    'model_id':   str(model.id),
                    'name':       model.name,
                    'would_retrain': True,
                    'reason':     check['retrain_reason'],
                })
            else:
                result = retrain_model(str(model.id), force=False)
                result['model_name'] = model.name
                results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description='AI Model Retraining')
    sub    = parser.add_subparsers(dest='command')

    # check
    check_p = sub.add_parser('check', help='Check if retraining needed')
    check_p.add_argument('--model-id', required=True)

    # run
    run_p = sub.add_parser('run', help='Run retraining')
    run_p.add_argument('--model-id',    required=True)
    run_p.add_argument('--dataset',     default='auto', help='Dataset path')
    run_p.add_argument('--force',       action='store_true')
    run_p.add_argument('--async',       action='store_true', dest='async_mode')

    # all
    all_p = sub.add_parser('all', help='Retrain all due models')
    all_p.add_argument('--tenant-id')
    all_p.add_argument('--dry-run', action='store_true')

    args = parser.parse_args()

    if args.command == 'check':
        result = check_retrain_needed(args.model_id)
        icon   = '⚠️ ' if result['needs_retrain'] else '✅'
        print(f"{icon} Model {args.model_id}:")
        print(f"   Needs retrain: {result['needs_retrain']}")
        print(f"   Drift status:  {result['drift_status']}")
        print(f"   Drift score:   {result['drift_score']:.4f}")
        print(f"   Reason:        {result['retrain_reason']}")

    elif args.command == 'run':
        print(f"\n🔄 Starting retrain for: {args.model_id}")
        result = retrain_model(args.model_id, args.dataset, args.force, args.async_mode)
        if result.get('skipped'):
            print(f"✅ Skipped: {result['reason']}")
        elif result.get('async'):
            print(f"✅ Async training queued: task_id={result.get('task_id')}")
        elif result['success']:
            print(f"✅ Retraining complete!")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    elif args.command == 'all':
        prefix = "DRY RUN — " if args.dry_run else ""
        print(f"\n{prefix}Checking all deployed models...")
        results = retrain_all_due(args.tenant_id, args.dry_run)
        if not results:
            print("✅ No models need retraining.")
        for r in results:
            status = r.get('reason', 'queued') if args.dry_run else ('✅' if r.get('success') else '❌')
            print(f"  {r.get('model_name', r.get('model_id', '?'))}: {status}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
