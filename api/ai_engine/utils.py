"""
api/ai_engine/utils.py
=======================
AI Engine — Utility Functions।
"""

import math
import hashlib
import json
import uuid
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache

from .constants import CHURN_RISK_BUCKETS, LTV_SEGMENTS

logger = logging.getLogger(__name__)


# ── Scoring Helpers ────────────────────────────────────────────────────

def get_churn_risk_level(probability: float) -> str:
    """Churn probability থেকে risk level বের করো।"""
    for level, (low, high) in CHURN_RISK_BUCKETS.items():
        if low <= probability < high:
            return level
    return 'very_high'


def get_ltv_segment(ltv: float) -> str:
    """LTV amount থেকে segment বের করো।"""
    for segment, (low, high) in LTV_SEGMENTS.items():
        if low <= ltv < high:
            return segment
    return 'premium'


def normalize_score(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Score কে 0-1 range এ normalize করো।"""
    if max_val == min_val:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def sigmoid(x: float) -> float:
    """Sigmoid activation function।"""
    return 1 / (1 + math.exp(-x))


def softmax(scores: List[float]) -> List[float]:
    """Softmax normalization।"""
    if not scores:
        return []
    max_score = max(scores)
    exps = [math.exp(s - max_score) for s in scores]
    total = sum(exps)
    return [e / total for e in exps] if total > 0 else scores


# ── Vector / Embedding Helpers ─────────────────────────────────────────

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """দুটি ভেক্টরের cosine similarity হিসাব করো।"""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a ** 2 for a in vec_a))
    norm_b = math.sqrt(sum(b ** 2 for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def euclidean_distance(vec_a: List[float], vec_b: List[float]) -> float:
    """দুটি ভেক্টরের euclidean distance।"""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return float('inf')
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))


def dot_product(vec_a: List[float], vec_b: List[float]) -> float:
    """Dot product হিসাব।"""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    return sum(a * b for a, b in zip(vec_a, vec_b))


# ── Cache Helpers ──────────────────────────────────────────────────────

def make_cache_key(*parts) -> str:
    """Cache key তৈরি করো।"""
    raw = ':'.join(str(p) for p in parts)
    return f"ai_engine:{hashlib.md5(raw.encode()).hexdigest()[:16]}:{raw[:80]}"


def cached(key: str, ttl: int, fn):
    """Simple cache-or-compute pattern।"""
    result = cache.get(key)
    if result is None:
        result = fn()
        cache.set(key, result, ttl)
    return result


# ── Feature Helpers ────────────────────────────────────────────────────

def safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division — ZeroDivisionError এড়াতে।"""
    if denominator == 0:
        return default
    return numerator / denominator


def days_since(dt: Optional[datetime]) -> int:
    """কত দিন আগে ছিল সেটা বের করো।"""
    if dt is None:
        return 9999
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return max(0, (now - dt).days)


def hours_since(dt: Optional[datetime]) -> float:
    """কত ঘণ্টা আগে।"""
    if dt is None:
        return 99999.0
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return max(0.0, (now - dt).total_seconds() / 3600)


def truncate_text(text: str, max_len: int = 200) -> str:
    """Text truncate করো।"""
    if not text:
        return ''
    return text[:max_len] + ('...' if len(text) > max_len else '')


# ── JSON / Data Helpers ────────────────────────────────────────────────

def safe_json_loads(data: Any, default=None) -> Any:
    """Safe JSON parse।"""
    if data is None:
        return default
    if isinstance(data, (dict, list)):
        return data
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """Nested dict কে flat করো feature engineering এর জন্য।"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """List কে chunks এ ভাগ করো batch processing এর জন্য।"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


# ── ID Generation ──────────────────────────────────────────────────────

def generate_request_id() -> str:
    """Unique request ID তৈরি করো।"""
    return str(uuid.uuid4())


def generate_run_id() -> str:
    """Experiment run ID।"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    short = str(uuid.uuid4())[:8]
    return f"run_{ts}_{short}"


# ── Metrics Helpers ────────────────────────────────────────────────────

def calculate_psi(expected: List[float], actual: List[float], buckets: int = 10) -> float:
    """
    Population Stability Index (PSI) হিসাব করো।
    Data drift detection এ ব্যবহার।
    PSI < 0.1  → No change
    PSI < 0.2  → Minor change
    PSI >= 0.2 → Major change
    """
    eps = 1e-6
    if not expected or not actual:
        return 0.0
    min_val = min(min(expected), min(actual))
    max_val = max(max(expected), max(actual))
    if min_val == max_val:
        return 0.0
    bucket_size = (max_val - min_val) / buckets
    psi = 0.0
    for i in range(buckets):
        low  = min_val + i * bucket_size
        high = low + bucket_size
        e_pct = len([x for x in expected if low <= x < high]) / max(len(expected), 1) + eps
        a_pct = len([x for x in actual   if low <= x < high]) / max(len(actual),   1) + eps
        psi += (a_pct - e_pct) * math.log(a_pct / e_pct)
    return round(psi, 6)


def precision_recall_f1(tp: int, fp: int, fn: int):
    """TP, FP, FN থেকে Precision, Recall, F1 হিসাব।"""
    precision = safe_ratio(tp, tp + fp)
    recall    = safe_ratio(tp, tp + fn)
    f1 = safe_ratio(2 * precision * recall, precision + recall)
    return round(precision, 4), round(recall, 4), round(f1, 4)


def weighted_score(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """Weighted average score হিসাব।"""
    total_weight = sum(weights.get(k, 0) for k in scores)
    if total_weight == 0:
        return 0.0
    return sum(scores.get(k, 0) * weights.get(k, 0) for k in scores) / total_weight
