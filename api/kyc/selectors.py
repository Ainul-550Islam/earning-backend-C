# kyc/selectors.py  ── WORLD #1
"""
Clean selector functions — read-only queries for views/services.
No DB writes here. Only SELECT.
"""
from django.db.models import QuerySet
from typing import Optional


def get_kyc_for_user(user) -> Optional['KYC']:
    from .models import KYC
    return KYC.objects.filter(user=user).first()


def get_latest_submission_for_user(user) -> Optional['KYCSubmission']:
    from .models import KYCSubmission
    return KYCSubmission.objects.filter(user=user).order_by('-submitted_at', '-created_at').first()


def get_kyc_by_id(kyc_id: int) -> Optional['KYC']:
    from .models import KYC
    try:
        return KYC.objects.select_related('user', 'reviewed_by', 'tenant').get(id=kyc_id)
    except KYC.DoesNotExist:
        return None


def get_kyc_admin_list(status: str = None, tenant=None, search: str = None,
                        doc_type: str = None, risk_min: int = None) -> QuerySet:
    from .models import KYC
    qs = KYC.objects.select_related('user').all().order_by('-created_at')
    if status:    qs = qs.filter(status=status)
    if tenant:    qs = qs.filter(tenant=tenant)
    if doc_type:  qs = qs.filter(document_type=doc_type)
    if risk_min is not None: qs = qs.filter(risk_score__gte=risk_min)
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(full_name__icontains=search) | Q(phone_number__icontains=search) |
            Q(document_number__icontains=search) | Q(user__username__icontains=search)
        )
    return qs


def get_pending_review_queue(tenant=None) -> QuerySet:
    from .models import KYC
    qs = KYC.objects.filter(status='pending').select_related('user').order_by('created_at')
    if tenant: qs = qs.filter(tenant=tenant)
    return qs


def get_kyc_dashboard_stats(tenant=None) -> dict:
    from .models import KYC
    from django.db.models import Count, Avg, Q
    from django.utils import timezone

    qs    = KYC.objects.all()
    if tenant: qs = qs.filter(tenant=tenant)
    today = timezone.now().date()

    return qs.aggregate(
        total=Count('id'),
        pending=Count('id',       filter=Q(status='pending')),
        verified=Count('id',      filter=Q(status='verified')),
        rejected=Count('id',      filter=Q(status='rejected')),
        not_submitted=Count('id', filter=Q(status='not_submitted')),
        expired=Count('id',       filter=Q(status='expired')),
        high_risk=Count('id',     filter=Q(risk_score__gt=60)),
        duplicates=Count('id',    filter=Q(is_duplicate=True)),
        submitted_today=Count('id', filter=Q(created_at__date=today)),
        avg_risk=Avg('risk_score'),
    )


def get_expiring_kycs(days: int = 30) -> QuerySet:
    from .models import KYC
    from django.utils import timezone
    import datetime
    deadline = timezone.now() + datetime.timedelta(days=days)
    return KYC.objects.filter(status='verified', expires_at__lte=deadline, expires_at__gte=timezone.now())


def get_duplicate_kycs() -> QuerySet:
    from .models import KYC
    return KYC.objects.filter(is_duplicate=True).select_related('user', 'duplicate_of')


def is_user_kyc_verified(user) -> bool:
    from .models import KYC
    from .utils.cache_utils import cache_get, cache_set
    from .constants import CacheKeys
    key = CacheKeys.KYC_USER_VERIFIED.format(user_id=user.id)
    cached = cache_get(key)
    if cached is not None: return cached
    result = KYC.objects.filter(user=user, status='verified').exists()
    cache_set(key, result, ttl=CacheKeys.TTL_VERIFIED)
    return result


def get_kyc_logs_for_user(user) -> QuerySet:
    from .models import KYC, KYCVerificationLog
    kyc = get_kyc_for_user(user)
    if not kyc: return KYCVerificationLog.objects.none()
    return kyc.kyc_kycverificationlog_tenant.all().order_by('-created_at')
