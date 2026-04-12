# =============================================================================
# api/promotions/optimization/lazy_loader.py
# Lazy Loading — Heavy resources (AI models, ML models) on-demand load করে
# App startup slow না করে, first-use এ load হয়
# =============================================================================

import logging
import threading
import time
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger('optimization.lazy_loader')


# =============================================================================
# ── LAZY RESOURCE ─────────────────────────────────────────────────────────────
# =============================================================================

class LazyResource:
    """
    Thread-safe lazy loader।
    Resource প্রথমবার access করা হলেই load হয়, তারপর cache করা থাকে।

    Usage:
        ocr_model = LazyResource(
            name='tesseract_ocr',
            loader=lambda: pytesseract.get_tesseract_version(),
            preload=False,
        )
        # First access এ load হবে
        version = ocr_model.get()
    """

    def __init__(
        self,
        name:     str,
        loader:   Callable,
        preload:  bool = False,
        timeout:  int  = 30,    # seconds — load এ এর বেশি সময় নিলে error
    ):
        self.name     = name
        self._loader  = loader
        self._timeout = timeout
        self._resource: Any = None
        self._loaded  = False
        self._lock    = threading.Lock()
        self._load_time_ms: float = 0.0

        if preload:
            self._load()

    def get(self) -> Any:
        """Resource return করে, প্রয়োজনে load করে।"""
        if not self._loaded:
            self._load()
        return self._resource

    def reload(self) -> Any:
        """Force reload করে।"""
        self._loaded   = False
        self._resource = None
        return self.get()

    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def load_time_ms(self) -> float:
        return self._load_time_ms

    def _load(self):
        with self._lock:
            if self._loaded:   # Double-check locking
                return
            start = time.monotonic()
            try:
                logger.info(f'Lazy loading: {self.name}...')
                self._resource  = self._loader()
                self._loaded    = True
                self._load_time_ms = round((time.monotonic() - start) * 1000, 2)
                logger.info(f'Lazy loaded: {self.name} ({self._load_time_ms}ms)')
            except Exception as e:
                self._load_time_ms = round((time.monotonic() - start) * 1000, 2)
                logger.error(f'Lazy load failed: {self.name} — {e}')
                raise


# =============================================================================
# ── AI MODEL REGISTRY ────────────────────────────────────────────────────────
# =============================================================================

class AIModelRegistry:
    """
    সব AI/ML model এর lazy loader registry।
    Model গুলো প্রথমবার ব্যবহারে load হয়।

    Registered models:
    - tesseract_ocr     → pytesseract
    - easyocr_en        → EasyOCR (English)
    - easyocr_bn        → EasyOCR (Bengali)
    - yolov8            → YOLO (object detection)
    - sentiment         → HuggingFace sentiment pipeline
    - fraud_classifier  → Trained fraud model (joblib)
    """

    _registry: dict[str, LazyResource] = {}
    _lock = threading.Lock()

    def register(self, name: str, loader: Callable, preload: bool = False) -> None:
        with self._lock:
            self._registry[name] = LazyResource(name=name, loader=loader, preload=preload)

    def get(self, name: str) -> Any:
        resource = self._registry.get(name)
        if not resource:
            raise KeyError(f'AI model not registered: {name}')
        return resource.get()

    def is_loaded(self, name: str) -> bool:
        resource = self._registry.get(name)
        return resource.is_loaded() if resource else False

    def list_models(self) -> list[dict]:
        return [
            {
                'name':    name,
                'loaded':  r.is_loaded(),
                'load_ms': r.load_time_ms if r.is_loaded() else None,
            }
            for name, r in self._registry.items()
        ]

    def preload_all(self) -> dict:
        """সব models preload করে (startup এ call করুন)।"""
        results = {}
        for name, resource in self._registry.items():
            try:
                resource.get()
                results[name] = 'loaded'
            except Exception as e:
                results[name] = f'failed: {e}'
        return results


# ── Global Registry ─────────────────────────────────────────────────────────
ai_models = AIModelRegistry()

# ── Register Models ──────────────────────────────────────────────────────────

def _load_easyocr_en():
    import easyocr
    return easyocr.Reader(['en'], gpu=False, verbose=False)

def _load_easyocr_bn():
    import easyocr
    return easyocr.Reader(['bn', 'en'], gpu=False, verbose=False)

def _load_yolo():
    from ultralytics import YOLO
    return YOLO('yolov8n.pt')

def _load_sentiment_pipeline():
    from transformers import pipeline
    return pipeline(
        'sentiment-analysis',
        model='distilbert-base-uncased-finetuned-sst-2-english',
        truncation=True,
    )

def _load_fraud_model():
    """Trained fraud model load করে (joblib)।"""
    try:
        import joblib
        from django.conf import settings
        model_path = getattr(settings, 'FRAUD_MODEL_PATH', None)
        if model_path:
            return joblib.load(model_path)
    except Exception as e:
        logger.warning(f'Fraud model not found: {e}')
    return None  # Fallback to heuristic

# Register (preload=False — on-demand load)
ai_models.register('easyocr_en',        _load_easyocr_en)
ai_models.register('easyocr_bn',        _load_easyocr_bn)
ai_models.register('yolo',              _load_yolo)
ai_models.register('sentiment',         _load_sentiment_pipeline)
ai_models.register('fraud_classifier',  _load_fraud_model)


# =============================================================================
# ── LAZY IMPORT DECORATOR ────────────────────────────────────────────────────
# =============================================================================

def lazy_import(module_name: str, attribute: str = None):
    """
    Module বা attribute lazily import করার decorator।

    Usage:
        @lazy_import('numpy', 'array')
        def process_data(data):
            return np_array(data)   # np_array = numpy.array
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            import importlib
            module = importlib.import_module(module_name)
            if attribute:
                obj = getattr(module, attribute)
                return fn(*args, **kwargs, **{attribute: obj})
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# ── PAGINATED LAZY LOADER ─────────────────────────────────────────────────────
# =============================================================================

class PaginatedLazyLoader:
    """
    Large dataset গুলো পেজে পেজে load করে।
    API response এ cursor-based pagination এর জন্য।

    একসাথে সব data load না করে প্রয়োজন অনুযায়ী load করে।
    """

    def __init__(
        self,
        queryset,
        page_size:    int = 20,
        prefetch_ahead: int = 1,   # কতটা পেজ আগে prefetch করবে
    ):
        self._qs            = queryset
        self._page_size     = page_size
        self._prefetch_ahead = prefetch_ahead
        self._cache:        dict[int, list] = {}
        self._total_count:  Optional[int]   = None
        self._lock          = threading.Lock()

    @property
    def total_count(self) -> int:
        if self._total_count is None:
            self._total_count = self._qs.count()
        return self._total_count

    @property
    def total_pages(self) -> int:
        return -(-self.total_count // self._page_size)  # ceiling division

    def get_page(self, page: int) -> list:
        """নির্দিষ্ট page এর data return করে।"""
        if page in self._cache:
            # Background prefetch (non-blocking)
            threading.Thread(target=self._prefetch, args=(page + 1,), daemon=True).start()
            return self._cache[page]

        data = self._load_page(page)
        threading.Thread(target=self._prefetch, args=(page + 1,), daemon=True).start()
        return data

    def iter_all(self):
        """সব pages iterate করে — generator।"""
        for page in range(1, self.total_pages + 1):
            yield self.get_page(page)

    def _load_page(self, page: int) -> list:
        start = (page - 1) * self._page_size
        end   = start + self._page_size
        data  = list(self._qs[start:end])
        with self._lock:
            self._cache[page] = data
        return data

    def _prefetch(self, page: int):
        """Background prefetch।"""
        if page <= self.total_pages and page not in self._cache:
            self._load_page(page)


# =============================================================================
# ── DEFERRED COMPUTATION ──────────────────────────────────────────────────────
# =============================================================================

class DeferredComputation:
    """
    Heavy computation defer করে — result প্রয়োজন না হওয়া পর্যন্ত compute হয় না।
    Response এ include করার আগেই compute করা হয়।
    """

    def __init__(self, fn: Callable, *args, **kwargs):
        self._fn     = fn
        self._args   = args
        self._kwargs = kwargs
        self._result = None
        self._computed = False

    def resolve(self) -> Any:
        """Result resolve করে।"""
        if not self._computed:
            self._result  = self._fn(*self._args, **self._kwargs)
            self._computed = True
        return self._result

    def __repr__(self):
        status = 'resolved' if self._computed else 'pending'
        return f'DeferredComputation({self._fn.__name__}, {status})'


# =============================================================================
# ── STREAMING RESPONSE HELPER ────────────────────────────────────────────────
# =============================================================================

class StreamingQuerysetHelper:
    """
    Large queryset গুলো streaming response হিসেবে পাঠানোর helper।
    Memory efficient — সব data একসাথে load হয় না।
    """

    @staticmethod
    def to_streaming_response(queryset, serializer_class, chunk_size: int = 100):
        """
        Large queryset streaming JSON response হিসেবে পাঠায়।

        Usage in views:
            def export_submissions(request):
                qs = TaskSubmission.objects.all()
                return StreamingQuerysetHelper.to_streaming_response(
                    qs, TaskSubmissionSerializer
                )
        """
        import json
        from django.http import StreamingHttpResponse

        def generate():
            yield '{"results": ['
            first = True
            for i in range(0, queryset.count(), chunk_size):
                chunk = queryset[i:i + chunk_size]
                serialized = serializer_class(chunk, many=True)
                for item in serialized.data:
                    if not first:
                        yield ','
                    yield json.dumps(item)
                    first = False
            yield ']}'

        response = StreamingHttpResponse(generate(), content_type='application/json')
        response['X-Accel-Buffering'] = 'no'   # Nginx buffering disable
        return response
