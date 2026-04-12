"""
api/ai_engine/SCRIPTS/evaluate_model.py
========================================
CLI — evaluate a trained model।
"""

import argparse, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

def main():
    parser = argparse.ArgumentParser(description='Evaluate AI Model')
    parser.add_argument('--model-id', required=True)
    args = parser.parse_args()
    import django; django.setup()
    from api.ai_engine.ML_PIPELINES.evaluation_pipeline import EvaluationPipeline
    result = EvaluationPipeline().run(args.model_id)
    print(f"Evaluation: {result}")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/deploy_model.py
=======================================
CLI — deploy a trained model to production।
"""

def main():
    import argparse, os, django
    parser = argparse.ArgumentParser(description='Deploy AI Model')
    parser.add_argument('--model-id',   required=True)
    parser.add_argument('--version-id', required=True)
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from api.ai_engine.ML_PIPELINES.deployment_pipeline import DeploymentPipeline
    result = DeploymentPipeline().deploy(args.model_id, args.version_id)
    print(f"Deploy result: {result}")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/monitor_model.py
========================================
CLI — monitor production model health।
"""

def main():
    import argparse, os, django
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--days', type=int, default=7)
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from api.ai_engine.ML_PIPELINES.monitoring_pipeline import MonitoringPipeline
    result = MonitoringPipeline().run(args.model_id)
    icon = '✅' if result['health'] == 'healthy' else '⚠️' if result['health'] == 'degraded' else '❌'
    print(f"{icon} Model health: {result['health']}")
    print(f"   Accuracy (7d): {result.get('accuracy_7d', 0):.1%}")
    for alert in result.get('alerts', []):
        print(f"   ⚠️  {alert}")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/retrain_model.py
=========================================
CLI — retrain a model (checks drift first)।
"""

def main():
    import argparse, os, django
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from api.ai_engine.ML_PIPELINES.retraining_pipeline import RetrainingPipeline
    pipeline = RetrainingPipeline()
    if not args.force and not pipeline.should_retrain(args.model_id):
        print("✅ No retraining needed.")
        return
    result = pipeline.run(args.model_id)
    print(f"Retrain result: {result}")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/update_features.py
==========================================
CLI — update feature store for all users।
"""

def main():
    import os, django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from api.ai_engine.tasks import task_update_user_embeddings
    result = task_update_user_embeddings()
    print(f"Features updated: {result}")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/run_experiment.py
=========================================
CLI — start an A/B test experiment।
"""

def main():
    import argparse, os, django
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment-id', required=True)
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from api.ai_engine.models import ABTestExperiment
    from django.utils import timezone
    ABTestExperiment.objects.filter(id=args.experiment_id).update(
        status='running', started_at=timezone.now()
    )
    print(f"✅ Experiment {args.experiment_id} started.")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/generate_predictions.py
===============================================
CLI — generate batch predictions for all users。
"""

def main():
    import argparse, os, django
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', default='churn', choices=['churn', 'ltv', 'fraud'])
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    if args.type == 'churn':
        from api.ai_engine.tasks import task_batch_churn_prediction
        result = task_batch_churn_prediction()
        print(f"Churn predictions: {result}")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/optimize_hyperparams.py
===============================================
CLI — hyperparameter optimization।
"""

def main():
    import argparse, os, django
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--n-iter', type=int, default=20)
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from api.ai_engine.ML_MODELS.hyperparameter_tuner import HyperparameterTuner
    from sklearn.ensemble import RandomForestClassifier
    import numpy as np

    # Placeholder — load real dataset in production
    X = np.random.randn(500, 10)
    y = np.random.randint(0, 2, 500)

    tuner = HyperparameterTuner()
    result = tuner.tune(
        RandomForestClassifier,
        X, y,
        param_grid={'n_estimators': list(range(50, 300, 50)), 'max_depth': [3, 5, 7, None]},
        n_iter=args.n_iter
    )
    print(f"Best params: {result['best_params']}")
    print(f"Best F1: {result['best_score']}")

if __name__ == '__main__': main()


"""
api/ai_engine/SCRIPTS/export_model.py
=======================================
CLI — export model for serving or archiving。
"""

def main():
    import argparse, os, django
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-id',  required=True)
    parser.add_argument('--output',    default='/tmp/exported_model')
    parser.add_argument('--format',    default='joblib', choices=['pickle', 'joblib'])
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    from api.ai_engine.MODEL_STORAGE.model_registry import ModelRegistry
    from api.ai_engine.MODEL_STORAGE.model_serializer import ModelSerializer

    registry = ModelRegistry()
    model    = registry.load(args.model_id)
    if model:
        path = ModelSerializer.serialize(model, args.output, fmt=args.format)
        print(f"✅ Model exported to: {path}")
    else:
        print(f"❌ Model not found: {args.model_id}")

if __name__ == '__main__': main()
