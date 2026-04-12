"""
api/ai_engine/config.py
========================
AI Engine — Configuration settings।
Django settings থেকে AI_ENGINE dict পড়ে।
"""

from django.conf import settings


def get_ai_config() -> dict:
    """
    settings.py তে AI_ENGINE dict define করো:

    AI_ENGINE = {
        'DEFAULT_MODEL_BACKEND': 'sklearn',
        'MODEL_STORAGE_PATH': '/models/',
        'ENABLE_GPU': False,
        'MAX_PREDICTION_BATCH': 256,
        'OPENAI_API_KEY': env('OPENAI_API_KEY', default=''),
        'ANTHROPIC_API_KEY': env('ANTHROPIC_API_KEY', default=''),
        'MLFLOW_TRACKING_URI': 'http://mlflow:5000',
        'FEATURE_STORE_BACKEND': 'django',  # 'redis' | 'feast' | 'django'
        'ENABLE_REAL_TIME_PREDICTION': True,
        'ENABLE_ASYNC_TRAINING': True,
        'CELERY_QUEUE': 'ai_tasks',
    }
    """
    return getattr(settings, 'AI_ENGINE', {})


class AIEngineConfig:
    """AI Engine configuration accessor।"""

    def __init__(self):
        self._cfg = get_ai_config()

    def get(self, key: str, default=None):
        return self._cfg.get(key, default)

    @property
    def model_storage_path(self) -> str:
        return self._cfg.get('MODEL_STORAGE_PATH', '/tmp/ai_models/')

    @property
    def default_backend(self) -> str:
        return self._cfg.get('DEFAULT_MODEL_BACKEND', 'sklearn')

    @property
    def enable_gpu(self) -> bool:
        return self._cfg.get('ENABLE_GPU', False)

    @property
    def max_prediction_batch(self) -> int:
        return self._cfg.get('MAX_PREDICTION_BATCH', 256)

    @property
    def openai_api_key(self) -> str:
        return self._cfg.get('OPENAI_API_KEY', '')

    @property
    def anthropic_api_key(self) -> str:
        return self._cfg.get('ANTHROPIC_API_KEY', '')

    @property
    def mlflow_tracking_uri(self) -> str:
        return self._cfg.get('MLFLOW_TRACKING_URI', '')

    @property
    def feature_store_backend(self) -> str:
        return self._cfg.get('FEATURE_STORE_BACKEND', 'django')

    @property
    def enable_real_time(self) -> bool:
        return self._cfg.get('ENABLE_REAL_TIME_PREDICTION', True)

    @property
    def celery_queue(self) -> str:
        return self._cfg.get('CELERY_QUEUE', 'ai_tasks')

    @property
    def enable_async_training(self) -> bool:
        return self._cfg.get('ENABLE_ASYNC_TRAINING', True)


# Singleton instance
ai_config = AIEngineConfig()
