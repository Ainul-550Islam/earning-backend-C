"""
api/ai_engine/SCRIPTS/monitor_model.py
=========================================
CLI Script — Production model health monitoring।
Accuracy, latency, drift, anomaly counts track করো।
Alerting ও scheduled reporting এর জন্য।
"""

import argparse
import os
import sys
import json
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def monitor_single_model(model_id: str, days: int = 7) -> dict:
    import django; django.setup()
    from api.ai_engine.ML_PIPELINES.monitoring_pipeline import MonitoringPipeline
    from api.ai_engine.TESTING_EVALUATION.online_evaluator import OnlineEvaluator

    pipeline_result = MonitoringPipeline().run(model_id)
    online_eval     = OnlineEvaluator(model_id).evaluate_window(hours=days * 24)
    latency_check   = OnlineEvaluator(model_id).monitor_latency()

    return {
        'model_id':         model_id,
        'days_analyzed':    days,
        'health':           pipeline_result.get('health', 'unknown'),
        'health_score':     pipeline_result.get('health_score', 0),
        'accuracy_7d':      online_eval.get('accuracy', 0),
        'total_predictions': online_eval.get('total', 0),
        'avg_latency_ms':   latency_check.get('avg_latency_ms', 0),
        'within_sla':       latency_check.get('within_sla', True),
        'drift_status':     pipeline_result.get('drift_status', 'unknown'),
        'alerts':           pipeline_result.get('alerts', []) + online_eval.get('alerts', []),
    }


def monitor_all_models(tenant_id: str = None) -> list:
    import django; django.setup()
    from api.ai_engine.models import AIModel
    qs = AIModel.objects.filter(status='deployed', is_active=True)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    results = []
    for model in qs:
        try:
            result = monitor_single_model(str(model.id))
            result['model_name'] = model.name
            results.append(result)
        except Exception as e:
            results.append({'model_id': str(model.id), 'error': str(e), 'health': 'error'})
    return results


def main():
    parser = argparse.ArgumentParser(description='AI Model Production Monitor')
    parser.add_argument('--model-id',   help='Specific model UUID (optional)')
    parser.add_argument('--tenant-id',  help='Tenant filter')
    parser.add_argument('--days',       type=int, default=7)
    parser.add_argument('--json',       action='store_true', help='JSON output')
    parser.add_argument('--alert-only', action='store_true', help='Only show alerts')
    args = parser.parse_args()

    if args.model_id:
        results = [monitor_single_model(args.model_id, args.days)]
    else:
        results = monitor_all_models(args.tenant_id)

    if args.alert_only:
        results = [r for r in results if r.get('alerts') or r.get('health') in ('degraded', 'critical', 'error')]

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return

    # Human-readable output
    print(f"\n{'='*70}")
    print(f"  AI ENGINE MODEL MONITORING REPORT  (last {args.days} days)")
    print(f"{'='*70}")
    print(f"  {'Model':<30} {'Health':<12} {'Acc':>6} {'Lat(ms)':>8} {'Drift':<10}")
    print(f"  {'-'*66}")

    overall_healthy = True
    for r in results:
        health  = r.get('health', 'unknown')
        icon    = '✅' if health == 'healthy' else '⚠️ ' if health == 'degraded' else '❌'
        name    = r.get('model_name', r.get('model_id', '?'))[:28]
        acc     = f"{r.get('accuracy_7d', 0):.1%}"
        lat     = f"{r.get('avg_latency_ms', 0):.0f}"
        drift   = r.get('drift_status', '?')[:9]
        print(f"  {icon} {name:<28} {health:<12} {acc:>6} {lat:>8} {drift:<10}")

        for alert in r.get('alerts', []):
            print(f"     ⚠️  {alert}")

        if health in ('degraded', 'critical', 'error'):
            overall_healthy = False

    print(f"\n  Total models: {len(results)}")
    print(f"  Overall: {'✅ ALL HEALTHY' if overall_healthy else '⚠️  ACTION REQUIRED'}")
    print(f"{'='*70}\n")

    if not overall_healthy:
        sys.exit(1)


if __name__ == '__main__':
    main()
