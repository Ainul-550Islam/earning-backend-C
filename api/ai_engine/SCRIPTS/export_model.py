"""
api/ai_engine/SCRIPTS/export_model.py
=======================================
CLI Script — Model export ও packaging।
Serving, archiving, deployment artifact তৈরি।
ONNX, joblib, pickle formats support।
"""

import argparse
import os
import sys
import json
import shutil
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def export_model(model_id: str, output_dir: str,
                  fmt: str = 'joblib',
                  include_metadata: bool = True) -> dict:
    """Model export করো — serving artifact তৈরি করো।"""
    import django; django.setup()
    from api.ai_engine.models import AIModel, ModelVersion
    from api.ai_engine.MODEL_STORAGE.model_registry import ModelRegistry
    from api.ai_engine.MODEL_STORAGE.model_serializer import ModelSerializer

    # Model ও version lookup
    try:
        model = AIModel.objects.get(id=model_id)
    except AIModel.DoesNotExist:
        return {'success': False, 'error': f'Model not found: {model_id}'}

    version = ModelVersion.objects.filter(
        ai_model_id=model_id, is_active=True
    ).first()

    if not version:
        return {'success': False, 'error': 'No active version found. Train first.'}

    # Output directory তৈরি
    os.makedirs(output_dir, exist_ok=True)
    model_filename = f"{model.name.replace(' ', '_').lower()}_v{version.version}.{fmt}"
    model_path     = os.path.join(output_dir, model_filename)

    # Model load করো
    registry   = ModelRegistry()
    model_obj  = registry.load(model_id, version.version)

    if model_obj is None:
        # Try loading from file path
        if version.model_file_path and os.path.exists(version.model_file_path):
            import pickle
            with open(version.model_file_path, 'rb') as f:
                model_obj = pickle.load(f)
        else:
            return {'success': False, 'error': 'Model file not found. Has training completed?'}

    # Serialize
    exported_path = ModelSerializer.serialize(model_obj, model_path, fmt=fmt)

    # Metadata export
    metadata = {}
    if include_metadata:
        metadata = {
            'model_id':    str(model.id),
            'model_name':  model.name,
            'algorithm':   model.algorithm,
            'task_type':   model.task_type,
            'version':     version.version,
            'accuracy':    float(version.accuracy),
            'f1_score':    float(version.f1_score),
            'auc_roc':     float(version.auc_roc),
            'feature_count': version.feature_count,
            'training_rows': version.training_rows,
            'trained_at':  str(version.trained_at),
            'export_format': fmt,
            'exported_file': model_filename,
        }
        meta_path = os.path.join(output_dir, 'model_metadata.json')
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    # File size
    size_mb = round(os.path.getsize(exported_path) / 1024 / 1024, 3) if os.path.exists(exported_path) else 0

    return {
        'success':      True,
        'model_path':   exported_path,
        'output_dir':   output_dir,
        'format':       fmt,
        'size_mb':      size_mb,
        'version':      version.version,
        'metadata':     metadata,
    }


def list_exportable_models() -> list:
    import django; django.setup()
    from api.ai_engine.models import AIModel, ModelVersion

    models  = AIModel.objects.filter(status='deployed', is_active=True)
    result  = []
    for m in models:
        v = ModelVersion.objects.filter(ai_model=m, is_active=True).first()
        result.append({
            'model_id':   str(m.id),
            'name':       m.name,
            'algorithm':  m.algorithm,
            'version':    v.version if v else 'none',
            'f1_score':   float(v.f1_score) if v else 0.0,
            'exportable': v is not None,
        })
    return result


def main():
    parser = argparse.ArgumentParser(description='Export AI Model Artifact')
    sub    = parser.add_subparsers(dest='command')

    # export
    exp_p = sub.add_parser('export', help='Export a model')
    exp_p.add_argument('--model-id',  required=True)
    exp_p.add_argument('--output',    default='/tmp/ai_exports', help='Output directory')
    exp_p.add_argument('--format',    default='joblib', choices=['pickle', 'joblib', 'onnx'])
    exp_p.add_argument('--no-meta',   action='store_true', help='Skip metadata export')

    # list
    list_p = sub.add_parser('list', help='List exportable models')

    args = parser.parse_args()

    if args.command == 'export':
        print(f"\n📦 Exporting model: {args.model_id}")
        print(f"   Format:    {args.format}")
        print(f"   Output:    {args.output}")

        result = export_model(
            args.model_id, args.output, args.format,
            include_metadata=not args.no_meta
        )

        if result['success']:
            print(f"\n✅ Export successful!")
            print(f"   File:      {result['model_path']}")
            print(f"   Size:      {result['size_mb']} MB")
            print(f"   Version:   {result['version']}")
            if result.get('metadata'):
                print(f"   Accuracy:  {result['metadata'].get('accuracy', 0):.3f}")
                print(f"   F1 Score:  {result['metadata'].get('f1_score', 0):.3f}")
        else:
            print(f"\n❌ Export failed: {result['error']}")
            sys.exit(1)

    elif args.command == 'list':
        models = list_exportable_models()
        print(f"\n{'Model Name':<30} {'Version':<10} {'F1':>6} {'Exportable'}")
        print("─" * 60)
        for m in models:
            exp = '✅' if m['exportable'] else '❌'
            print(f"{m['name'][:28]:<30} {m['version']:<10} {m['f1_score']:>5.3f}  {exp}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
