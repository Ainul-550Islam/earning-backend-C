"""
api/ai_engine/validators.py
============================
AI Engine — Input validation helpers।
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .constants import (
    MAX_TEXT_LENGTH, MIN_TEXT_LENGTH, MAX_IMAGE_SIZE_MB,
    SUPPORTED_IMAGE_FORMATS, SUPPORTED_LANGUAGES,
)


def validate_probability(value: float):
    """0.0 থেকে 1.0 এর মধ্যে না হলে error।"""
    if not (0.0 <= value <= 1.0):
        raise ValidationError(_('Probability must be between 0.0 and 1.0.'))


def validate_embedding_vector(vector):
    """Embedding vector validate করো।"""
    if not isinstance(vector, list):
        raise ValidationError(_('Embedding vector must be a list of floats.'))
    if len(vector) == 0:
        raise ValidationError(_('Embedding vector cannot be empty.'))
    if not all(isinstance(v, (int, float)) for v in vector):
        raise ValidationError(_('Embedding vector must contain only numbers.'))
    if len(vector) > 4096:
        raise ValidationError(_('Embedding vector too large (max 4096 dimensions).'))


def validate_text_input(text: str):
    """NLP input text validate করো।"""
    if not text or not text.strip():
        raise ValidationError(_('Text input cannot be empty.'))
    if len(text) < MIN_TEXT_LENGTH:
        raise ValidationError(_(f'Text too short (minimum {MIN_TEXT_LENGTH} characters).'))
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(_(f'Text too long (maximum {MAX_TEXT_LENGTH} characters).'))


def validate_feature_dict(features: dict):
    """Feature dictionary validate করো।"""
    if not isinstance(features, dict):
        raise ValidationError(_('Features must be a dictionary.'))
    if len(features) == 0:
        raise ValidationError(_('Feature dictionary cannot be empty.'))
    for key, value in features.items():
        if not isinstance(key, str):
            raise ValidationError(_(f'Feature key must be a string: {key}'))
        if not isinstance(value, (int, float, bool, str, type(None))):
            raise ValidationError(_(f'Feature value must be scalar: {key}'))


def validate_hyperparameters(params: dict):
    """Hyperparameter dict validate করো।"""
    if not isinstance(params, dict):
        raise ValidationError(_('Hyperparameters must be a dictionary.'))


def validate_model_version_format(version: str):
    """Version string format validate (semver-like)।"""
    import re
    pattern = r'^\d+\.\d+(\.\d+)?$'
    if not re.match(pattern, version):
        raise ValidationError(_(f'Invalid version format: {version}. Use X.Y or X.Y.Z'))


def validate_language_code(lang: str):
    """Supported language code validate।"""
    if lang not in SUPPORTED_LANGUAGES:
        raise ValidationError(_(f'Unsupported language: {lang}. Supported: {SUPPORTED_LANGUAGES}'))


def validate_ab_test_split(control: int, treatment: int):
    """A/B test traffic split validate।"""
    if control + treatment != 100:
        raise ValidationError(_('A/B test traffic split must sum to 100%.'))
    if control < 10 or treatment < 10:
        raise ValidationError(_('Each variant must have at least 10% traffic.'))


def validate_cluster_count(n: int):
    """K-means cluster count validate।"""
    if not (2 <= n <= 50):
        raise ValidationError(_('Number of clusters must be between 2 and 50.'))
