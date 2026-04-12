# kyc/billing/views.py  ── WORLD #1
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from .models import KYCPlan, KYCSubscription, KYCUsageRecord, KYCInvoice, APIKey


# ── Public endpoints ───────────────────────────────────────

@api_view(['GET'])
def plans_list(request):
    """List all available KYC plans — public"""
    plans = KYCPlan.objects.filter(is_active=True).order_by('sort_order')
    return Response([{
        'id':                p.id,
        'name':              p.name,
        'plan_type':         p.plan_type,
        'monthly_price_bdt': str(p.monthly_price_bdt),
        'per_kyc_price_bdt': str(p.per_kyc_price_bdt),
        'monthly_kyc_limit': p.monthly_kyc_limit,
        'features':          p.features,
        'kyb_enabled':       p.kyb_enabled,
        'video_kyc_enabled': p.video_kyc_enabled,
        'aml_enabled':       p.aml_enabled,
        'sla_hours':         p.sla_hours,
    } for p in plans])


# ── Tenant subscription endpoints ──────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    """Current subscription info"""
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant'}, status=400)
    try:
        sub = KYCSubscription.objects.select_related('plan').get(tenant=tenant)
    except KYCSubscription.DoesNotExist:
        return Response({'status': 'no_subscription', 'message': 'No active subscription'})

    # Current month usage
    now   = timezone.now()
    usage = KYCUsageRecord.objects.filter(
        tenant=tenant, created_at__year=now.year, created_at__month=now.month
    ).values('usage_type').distinct()

    return Response({
        'plan':              sub.plan.name,
        'plan_type':         sub.plan.plan_type,
        'status':            sub.status,
        'is_trial':          sub.is_trial,
        'trial_ends_at':     sub.trial_ends_at,
        'next_billing_date': sub.next_billing_date,
        'days_until_renewal': sub.days_until_renewal,
        'monthly_price_bdt': str(sub.plan.monthly_price_bdt),
        'auto_renew':        sub.auto_renew,
        'features': {
            'kyb_enabled':            sub.plan.kyb_enabled,
            'video_kyc_enabled':      sub.plan.video_kyc_enabled,
            'aml_enabled':            sub.plan.aml_enabled,
            'perpetual_kyc_enabled':  sub.plan.perpetual_kyc_enabled,
            'behavioral_enabled':     sub.plan.behavioral_enabled,
            'custom_branding':        sub.plan.custom_branding,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_usage(request):
    """Current month usage summary"""
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant'}, status=400)
    now  = timezone.now()
    from django.db.models import Sum, Count
    qs   = KYCUsageRecord.objects.filter(
        tenant=tenant, created_at__year=now.year, created_at__month=now.month
    )
    by_type = qs.values('usage_type').annotate(count=Count('id'), total=Sum('total_bdt'))
    return Response({
        'period':    f"{now.year}-{now.month:02d}",
        'total_bdt': str(qs.aggregate(t=Sum('total_bdt'))['t'] or 0),
        'breakdown': list(by_type),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_invoices(request):
    """User's invoices"""
    tenant   = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant'}, status=400)
    invoices = KYCInvoice.objects.filter(tenant=tenant).order_by('-created_at')[:12]
    return Response([{
        'invoice_number': i.invoice_number,
        'status':         i.status,
        'period':         f"{i.period_start} to {i.period_end}",
        'total_bdt':      str(i.total_bdt),
        'issued_at':      i.issued_at,
        'due_date':       i.due_date,
        'paid_at':        i.paid_at,
        'pdf_url':        i.pdf_file.url if i.pdf_file else None,
    } for i in invoices])


# ── API Key management ─────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_keys(request):
    """List / create API keys"""
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant'}, status=400)

    if request.method == 'GET':
        keys = APIKey.objects.filter(tenant=tenant, is_active=True)
        return Response([{
            'id':          k.id,
            'name':        k.name,
            'key_type':    k.key_type,
            'key_prefix':  k.key_prefix + '...',
            'is_valid':    k.is_valid,
            'last_used_at': k.last_used_at,
            'expires_at':  k.expires_at,
            'created_at':  k.created_at,
        } for k in keys])

    # POST — generate new key
    name     = request.data.get('name', 'My API Key')
    key_type = request.data.get('key_type', 'test')
    instance, raw_key = APIKey.generate(tenant=tenant, name=name, key_type=key_type, created_by=request.user)
    return Response({
        'id':       instance.id,
        'name':     instance.name,
        'key_type': instance.key_type,
        'api_key':  raw_key,
        'warning':  'This key will only be shown ONCE. Store it securely.',
    }, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def revoke_api_key(request, key_id):
    """Revoke an API key"""
    tenant = getattr(request.user, 'tenant', None)
    try:
        key = APIKey.objects.get(id=key_id, tenant=tenant)
        key.is_active  = False
        key.revoked_at = timezone.now()
        key.save()
        return Response({'message': 'API key revoked'})
    except APIKey.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)


# ── Admin billing endpoints ────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_subscriptions(request):
    """Admin — All subscriptions"""
    qs = KYCSubscription.objects.select_related('tenant', 'plan').all().order_by('-created_at')
    status_f = request.query_params.get('status')
    if status_f: qs = qs.filter(status=status_f)
    return Response([{
        'tenant':        str(s.tenant),
        'plan':          s.plan.name,
        'status':        s.status,
        'is_trial':      s.is_trial,
        'monthly_price': str(s.plan.monthly_price_bdt),
        'next_billing':  s.next_billing_date,
    } for s in qs[:100]])


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_revenue(request):
    """Admin — Revenue summary"""
    from django.db.models import Sum
    now = timezone.now()
    this_month = KYCInvoice.objects.filter(
        created_at__year=now.year, created_at__month=now.month
    ).aggregate(total=Sum('total_bdt'))
    this_year = KYCInvoice.objects.filter(
        created_at__year=now.year, status='paid'
    ).aggregate(total=Sum('total_bdt'))
    active_subs = KYCSubscription.objects.filter(status__in=['active','trial']).count()
    return Response({
        'this_month_bdt':     str(this_month['total'] or 0),
        'this_year_paid_bdt': str(this_year['total'] or 0),
        'active_subscriptions': active_subs,
        'mrr_bdt':            str(
            KYCSubscription.objects.filter(status='active').aggregate(
                mrr=Sum('plan__monthly_price_bdt')
            )['mrr'] or 0
        ),
    })
