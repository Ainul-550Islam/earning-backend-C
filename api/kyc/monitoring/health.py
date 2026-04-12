# kyc/monitoring/health.py  ── WORLD #1
"""
System health monitoring for KYC service.
Used by load balancers, Kubernetes probes, uptime monitors.
GET /api/kyc/health/           → Basic
GET /api/kyc/health/deep/      → Full system check
GET /api/kyc/health/providers/ → External provider status
"""
import time
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def check_database() -> dict:
    """Check DB connectivity and response time."""
    start = time.time()
    try:
        from kyc.models import KYCFeatureFlag
        KYCFeatureFlag.objects.count()
        return {'status': 'ok', 'latency_ms': int((time.time()-start)*1000)}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_redis() -> dict:
    """Check Redis/cache connectivity."""
    start = time.time()
    try:
        from django.core.cache import cache
        cache.set('kyc_health_check', '1', timeout=5)
        val = cache.get('kyc_health_check')
        if val != '1': raise ValueError('Cache read mismatch')
        return {'status': 'ok', 'latency_ms': int((time.time()-start)*1000)}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_celery() -> dict:
    """Check Celery worker availability."""
    try:
        from celery.app.control import Control
        from django.conf import settings
        app = __import__(settings.CELERY_APP if hasattr(settings,'CELERY_APP') else 'celery').current_app
        ctrl = Control(app)
        workers = ctrl.ping(timeout=2)
        return {'status': 'ok', 'workers': len(workers)} if workers else {'status': 'degraded', 'workers': 0}
    except Exception as e:
        return {'status': 'unknown', 'error': str(e)}


def check_storage() -> dict:
    """Check file storage (S3/local)."""
    start = time.time()
    try:
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        test_path = 'kyc/health/check.txt'
        default_storage.save(test_path, ContentFile(b'ok'))
        default_storage.delete(test_path)
        return {'status': 'ok', 'latency_ms': int((time.time()-start)*1000)}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_ocr_provider() -> dict:
    """Check configured OCR provider."""
    from django.conf import settings
    provider = getattr(settings, 'KYC_OCR_PROVIDER_PRIORITY', ['tesseract'])[0]
    if provider == 'google_vision':
        key = getattr(settings, 'GOOGLE_APPLICATION_CREDENTIALS', '')
        return {'status': 'ok' if key else 'misconfigured', 'provider': provider}
    if provider == 'aws_textract':
        import os
        key = os.getenv('AWS_ACCESS_KEY_ID','')
        return {'status': 'ok' if key else 'misconfigured', 'provider': provider}
    return {'status': 'ok', 'provider': 'tesseract (local)'}


def check_aml_provider() -> dict:
    """Check AML screening provider."""
    from django.conf import settings
    key = getattr(settings, 'COMPLYADVANTAGE_API_KEY', '')
    if key:
        return {'status': 'configured', 'provider': 'complyadvantage'}
    return {'status': 'local_only', 'provider': 'local_db', 'note': 'Using local sanctions DB only'}


def get_system_stats() -> dict:
    """Quick system stats for health dashboard."""
    try:
        from kyc.models import KYC, KYCSubmission
        from django.db.models import Count, Q
        today = timezone.now().date()
        return {
            'total_kyc':        KYC.objects.count(),
            'pending_review':   KYC.objects.filter(status='pending').count(),
            'verified_today':   KYC.objects.filter(reviewed_at__date=today, status='verified').count(),
            'submitted_today':  KYC.objects.filter(created_at__date=today).count(),
            'high_risk':        KYC.objects.filter(risk_score__gt=60).count(),
        }
    except Exception:
        return {}


# Views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_basic(request):
    """Basic liveness probe — just returns 200 if service is up."""
    return Response({'status': 'ok', 'service': 'kyc', 'version': '2.0.0', 'timestamp': timezone.now().isoformat()})


@api_view(['GET'])
@permission_classes([AllowAny])
def health_deep(request):
    """Full system health check — DB, cache, storage, workers."""
    checks = {
        'database': check_database(),
        'cache':    check_redis(),
        'storage':  check_storage(),
        'celery':   check_celery(),
    }
    overall = 'ok' if all(c.get('status') in ('ok','unknown','degraded') for c in checks.values()) else 'error'
    status_code = 200 if overall == 'ok' else 503
    return Response({
        'status':    overall,
        'timestamp': timezone.now().isoformat(),
        'checks':    checks,
        'stats':     get_system_stats(),
    }, status=status_code)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def health_providers(request):
    """External provider health — OCR, face match, AML."""
    return Response({
        'ocr_provider':  check_ocr_provider(),
        'aml_provider':  check_aml_provider(),
        'timestamp':     timezone.now().isoformat(),
    })
