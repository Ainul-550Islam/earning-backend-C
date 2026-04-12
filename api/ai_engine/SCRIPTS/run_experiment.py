"""
api/ai_engine/SCRIPTS/run_experiment.py
=========================================
CLI Script — A/B Test Experiment management।
Start, stop, analyze, winner declare করো।
Schedule: manual trigger বা CI/CD pipeline থেকে।
"""

import argparse
import os
import sys
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_experiment(experiment_id: str) -> dict:
    import django; django.setup()
    from api.ai_engine.models import ABTestExperiment
    from django.utils import timezone

    try:
        exp = ABTestExperiment.objects.get(id=experiment_id)
        if exp.status not in ('draft', 'paused'):
            return {'success': False, 'error': f'Cannot start experiment in status: {exp.status}'}
        exp.status     = 'running'
        exp.started_at = timezone.now()
        exp.save(update_fields=['status', 'started_at'])
        return {'success': True, 'status': 'running', 'name': exp.name}
    except ABTestExperiment.DoesNotExist:
        return {'success': False, 'error': f'Experiment not found: {experiment_id}'}


def stop_experiment(experiment_id: str) -> dict:
    import django; django.setup()
    from api.ai_engine.models import ABTestExperiment
    from api.ai_engine.TESTING_EVALUATION.ab_test_evaluator import ABTestEvaluator
    from django.utils import timezone

    try:
        exp             = ABTestExperiment.objects.get(id=experiment_id)
        exp.status      = 'completed'
        exp.ended_at    = timezone.now()
        exp.save(update_fields=['status', 'ended_at'])

        # Auto-analyze
        eval_result = ABTestEvaluator().evaluate(experiment_id)
        return {
            'success':     True,
            'status':      'completed',
            'winner':      eval_result.get('winner', 'pending'),
            'confidence':  eval_result.get('confidence', 0),
            'lift_pct':    eval_result.get('lift_pct', 0),
        }
    except ABTestExperiment.DoesNotExist:
        return {'success': False, 'error': f'Experiment not found: {experiment_id}'}


def analyze_experiment(experiment_id: str) -> dict:
    import django; django.setup()
    from api.ai_engine.TESTING_EVALUATION.ab_test_evaluator import ABTestEvaluator
    return ABTestEvaluator().evaluate(experiment_id)


def list_experiments(status: str = None) -> list:
    import django; django.setup()
    from api.ai_engine.models import ABTestExperiment
    qs = ABTestExperiment.objects.all().order_by('-created_at')
    if status:
        qs = qs.filter(status=status)
    return [
        {'id': str(e.id), 'name': e.name, 'status': e.status,
         'winner': e.winner, 'started_at': str(e.started_at)}
        for e in qs[:20]
    ]


def main():
    parser = argparse.ArgumentParser(description='A/B Test Experiment Management')
    sub    = parser.add_subparsers(dest='command')

    # start
    start_p = sub.add_parser('start', help='Start an experiment')
    start_p.add_argument('--id', required=True, help='Experiment UUID')

    # stop
    stop_p = sub.add_parser('stop', help='Stop and analyze experiment')
    stop_p.add_argument('--id', required=True, help='Experiment UUID')

    # analyze
    analyze_p = sub.add_parser('analyze', help='Analyze running experiment')
    analyze_p.add_argument('--id', required=True, help='Experiment UUID')

    # list
    list_p = sub.add_parser('list', help='List experiments')
    list_p.add_argument('--status', choices=['draft','running','completed','paused'])

    args = parser.parse_args()

    if args.command == 'start':
        result = start_experiment(args.id)
        if result['success']:
            print(f"✅ Experiment started: {result.get('name')}")
        else:
            print(f"❌ {result['error']}"); sys.exit(1)

    elif args.command == 'stop':
        result = stop_experiment(args.id)
        if result['success']:
            print(f"✅ Experiment completed")
            print(f"   Winner:     {result.get('winner', 'pending')}")
            print(f"   Confidence: {result.get('confidence', 0):.1%}")
            print(f"   Lift:       {result.get('lift_pct', 0):.2f}%")
        else:
            print(f"❌ {result['error']}"); sys.exit(1)

    elif args.command == 'analyze':
        result = analyze_experiment(args.id)
        print(f"📊 Experiment Analysis:")
        for k, v in result.items():
            print(f"   {k}: {v}")

    elif args.command == 'list':
        exps = list_experiments(getattr(args, 'status', None))
        print(f"\n{'ID':<36} {'Name':<30} {'Status':<12} {'Winner':<12}")
        print("─" * 95)
        for e in exps:
            print(f"{e['id']:<36} {e['name'][:28]:<30} {e['status']:<12} {e.get('winner','─'):<12}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
