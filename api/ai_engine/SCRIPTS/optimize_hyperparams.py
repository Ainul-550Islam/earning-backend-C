"""
api/ai_engine/SCRIPTS/optimize_hyperparams.py
===============================================
CLI Script — Automated Hyperparameter Optimization।
Grid search, random search, Bayesian optimization।
Best params খুঁজে DB তে save করো।
"""

import argparse
import os
import sys
import json
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Hyperparameter search spaces per algorithm ───────────────────────────────
SEARCH_SPACES = {
    'xgboost': {
        'n_estimators':     [50, 100, 200, 300, 500],
        'max_depth':        [3, 4, 5, 6, 7, 8],
        'learning_rate':    [0.01, 0.05, 0.1, 0.15, 0.2],
        'subsample':        [0.6, 0.7, 0.8, 0.9, 1.0],
        'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
        'min_child_weight': [1, 3, 5, 7],
    },
    'lightgbm': {
        'n_estimators':     [100, 200, 300, 500],
        'num_leaves':       [15, 31, 63, 127],
        'learning_rate':    [0.01, 0.05, 0.1, 0.15],
        'min_child_samples': [10, 20, 30, 50],
        'subsample':        [0.6, 0.8, 1.0],
    },
    'random_forest': {
        'n_estimators':     [100, 200, 300, 500],
        'max_depth':        [None, 5, 10, 15, 20],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf':  [1, 2, 4],
        'max_features':     ['sqrt', 'log2', None],
    },
    'logistic_reg': {
        'C':            [0.001, 0.01, 0.1, 1.0, 10.0, 100.0],
        'penalty':      ['l1', 'l2', 'elasticnet'],
        'solver':       ['lbfgs', 'liblinear', 'saga'],
        'max_iter':     [100, 200, 500],
    },
}


def optimize_hyperparams(model_id: str, method: str = 'random',
                           n_iter: int = 20, cv: int = 3,
                           dataset_path: str = None,
                           scoring: str = 'f1_weighted') -> dict:
    """Hyperparameter optimization চালাও।"""
    import django; django.setup()

    from api.ai_engine.models import AIModel
    from api.ai_engine.ML_MODELS.hyperparameter_tuner import HyperparameterTuner
    from api.ai_engine.ML_MODELS.data_preprocessor import DataPreprocessor
    from api.ai_engine.ML_MODELS.data_splitter import DataSplitter

    # Model load
    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return {'success': False, 'error': f'Model not found: {model_id}'}

    algorithm = model.algorithm
    param_grid = SEARCH_SPACES.get(algorithm, SEARCH_SPACES['random_forest'])

    print(f"Optimizing: {model.name} [{algorithm}]")
    print(f"Method:     {method} | Iterations: {n_iter} | CV: {cv}")
    print(f"Search space: {len(param_grid)} hyperparameters")
    print()

    # Generate synthetic data if no dataset provided
    if dataset_path:
        import pandas as pd
        df = pd.read_csv(dataset_path)
        target = model.target_column or df.columns[-1]
        result = DataPreprocessor().preprocess(df.to_dict('records'), target)
        if 'error' in result:
            return {'success': False, 'error': result['error']}
        X_data = result['X'].values
        y_data = result['y'].values
    else:
        import numpy as np
        logger.warning("No dataset provided — using synthetic data for demo")
        n_samples = max(1000, n_iter * 50)
        X_data    = np.random.randn(n_samples, 10)
        y_data    = np.random.randint(0, 2, n_samples)

    # Split data
    from sklearn.ensemble import RandomForestClassifier
    model_class = RandomForestClassifier  # default

    try:
        if algorithm == 'xgboost':
            from xgboost import XGBClassifier
            model_class = XGBClassifier
        elif algorithm == 'lightgbm':
            from lightgbm import LGBMClassifier
            model_class = LGBMClassifier
    except ImportError:
        logger.warning(f"{algorithm} not installed — using RandomForest")

    # Run optimization
    print(f"Running {method} search ({n_iter} iterations)...")
    tuner  = HyperparameterTuner()
    result = tuner.tune(
        model_class=model_class,
        X_train=X_data,
        y_train=y_data,
        param_grid=param_grid,
        method=method,
        n_iter=n_iter,
        cv=cv,
    )

    if 'error' in result:
        return {'success': False, 'error': result['error']}

    # Save best params to model
    best_params = result['best_params']
    AIModel.objects.filter(id=model_id).update(hyperparameters=best_params)
    print(f"\n✅ Best params saved to model: {model.name}")

    return {
        'success':      True,
        'model_id':     model_id,
        'model_name':   model.name,
        'algorithm':    algorithm,
        'method':       method,
        'n_iter':       n_iter,
        'best_params':  best_params,
        'best_score':   result.get('best_score', 0),
        'scoring':      scoring,
    }


def compare_models(model_ids: list, n_iter: int = 10) -> list:
    """Multiple models এর best params compare করো।"""
    results = []
    for mid in model_ids:
        result = optimize_hyperparams(mid, method='random', n_iter=n_iter)
        results.append(result)
    # Sort by best score
    return sorted(results, key=lambda x: x.get('best_score', 0), reverse=True)


def main():
    parser = argparse.ArgumentParser(description='Hyperparameter Optimization')
    sub    = parser.add_subparsers(dest='command')

    # optimize
    opt_p = sub.add_parser('optimize', help='Optimize a model')
    opt_p.add_argument('--model-id',  required=True)
    opt_p.add_argument('--method',    default='random', choices=['random', 'grid', 'bayesian'])
    opt_p.add_argument('--n-iter',    type=int, default=20)
    opt_p.add_argument('--cv',        type=int, default=3)
    opt_p.add_argument('--dataset',   help='CSV dataset path')
    opt_p.add_argument('--scoring',   default='f1_weighted')

    # compare
    cmp_p = sub.add_parser('compare', help='Compare multiple models')
    cmp_p.add_argument('--model-ids', nargs='+', required=True)
    cmp_p.add_argument('--n-iter',    type=int, default=10)

    # show-spaces
    sp_p = sub.add_parser('show-spaces', help='Show search spaces')
    sp_p.add_argument('--algorithm', choices=list(SEARCH_SPACES.keys()))

    args = parser.parse_args()

    if args.command == 'optimize':
        result = optimize_hyperparams(
            model_id=args.model_id,
            method=args.method,
            n_iter=args.n_iter,
            cv=args.cv,
            dataset_path=args.dataset,
            scoring=args.scoring,
        )
        if result['success']:
            print(f"\n{'='*60}")
            print(f"✅ Optimization Complete!")
            print(f"   Model:      {result['model_name']}")
            print(f"   Algorithm:  {result['algorithm']}")
            print(f"   Best Score: {result['best_score']:.4f}")
            print(f"   Best Params:")
            for k, v in result['best_params'].items():
                print(f"     {k}: {v}")
        else:
            print(f"❌ Failed: {result['error']}")
            sys.exit(1)

    elif args.command == 'compare':
        results = compare_models(args.model_ids, args.n_iter)
        print(f"\n{'Model':<36} {'Score':>8} {'Algorithm':<15}")
        print('─' * 65)
        for r in results:
            if r.get('success'):
                print(f"{r['model_id']:<36} {r.get('best_score', 0):>8.4f} {r.get('algorithm', '?'):<15}")

    elif args.command == 'show-spaces':
        algo = args.algorithm
        spaces = {algo: SEARCH_SPACES[algo]} if algo else SEARCH_SPACES
        for alg, space in spaces.items():
            print(f"\n{alg}:")
            for param, values in space.items():
                print(f"  {param}: {values}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
