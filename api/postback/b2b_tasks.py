"""b2b_tasks.py — Celery tasks for the B2B system."""
import logging, json, hmac, hashlib
import requests
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def dispatch_outbound_webhook(self, subscription_id: str, event_type: str, payload: dict):
    from .b2b_models import OutboundWebhookSubscription
    try:
        sub = OutboundWebhookSubscription.objects.get(pk=subscription_id, is_active=True)
    except OutboundWebhookSubscription.DoesNotExist:
        return
    if event_type not in sub.event_types and "all" not in sub.event_types:
        return
    body = json.dumps({**payload, "event": event_type, "timestamp": timezone.now().isoformat()}).encode()
    sig = sub.build_signature(body)
    try:
        resp = requests.post(
            sub.endpoint_url,
            data=body,
            headers={"Content-Type": "application/json", "X-Webhook-Sig": sig,
                     "X-Event-Type": event_type},
            timeout=10,
        )
        if resp.ok:
            sub.record_success()
        else:
            sub.record_failure()
            raise self.retry(countdown=60 * (self.request.retries + 1))
    except requests.RequestException as exc:
        sub.record_failure()
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2)
def generate_monthly_invoices(self):
    """Run on 1st of month — generate B2BInvoice for all active publishers/advertisers."""
    import datetime
    from django.db.models import Sum, Count
    from .b2b_models import OrganizationAccount, B2BInvoice, RevenueShareRule
    from postback.models import PostbackLog

    today = datetime.date.today()
    period_end = today.replace(day=1) - datetime.timedelta(days=1)
    period_start = period_end.replace(day=1)
    created = 0

    for org in OrganizationAccount.objects.filter(status="active"):
        if B2BInvoice.objects.filter(organization=org, period_start=period_start).exists():
            continue
        networks = list(org.networks.values_list("id", flat=True)) if hasattr(org, "networks") else []
        agg = PostbackLog.objects.filter(
            network_id__in=networks,
            received_at__date__gte=period_start,
            received_at__date__lte=period_end,
            status="rewarded",
        ).aggregate(total=Sum("payout"), count=Count("id"))
        gross = agg["total"] or 0
        conversions = agg["count"] or 0
        if not gross:
            continue
        rule = RevenueShareRule.objects.filter(organization=org, is_active=True).first()
        payout = rule.calculate_publisher_payout(gross) if rule else gross * 70 / 100
        invoice_type = "publisher_payout" if org.account_type == "publisher" else "advertiser_charge"
        B2BInvoice.objects.create(
            organization=org, invoice_type=invoice_type, status="draft",
            period_start=period_start, period_end=period_end,
            subtotal_bdt=payout, conversions=conversions,
            line_items=[{"description": f"Conversions {period_start}–{period_end}",
                         "quantity": conversions, "unit_price_bdt": str(gross / conversions if conversions else 0),
                         "total_bdt": str(payout)}],
        )
        created += 1
    logger.info("Monthly invoices generated: %d", created)
    return {"invoices_created": created, "period": str(period_start)}


@shared_task(bind=True)
def check_budget_caps(self):
    """Sweep all active AdvertiserBudgetCaps and alert/pause when threshold hit."""
    from .b2b_models import AdvertiserBudgetCap
    from .tasks import send_push_notification
    for cap in AdvertiserBudgetCap.objects.filter(is_active=True):
        pct = cap.utilisation_pct
        if pct >= 100:
            cap.is_active = False
            cap.save(update_fields=["is_active"])
            logger.warning("Budget cap EXHAUSTED: org=%s cap=%s", cap.organization_id, cap.pk)
        elif pct >= cap.alert_threshold_pct:
            logger.info("Budget cap alert: org=%s at %.1f%%", cap.organization_id, pct)


@shared_task(bind=True)
def rebuild_b2b_analytics(self):
    """Pre-compute per-org conversion totals for the B2B dashboard."""
    from .b2b_models import OrganizationAccount, PartnerCreditLedger
    from postback.models import PostbackLog
    from django.db.models import Sum, Count
    import datetime
    since = timezone.now() - datetime.timedelta(days=30)
    for org in OrganizationAccount.objects.filter(status="active"):
        networks = list(org.networks.values_list("id", flat=True)) if hasattr(org, "networks") else []
        agg = PostbackLog.objects.filter(
            network_id__in=networks, received_at__gte=since, status="rewarded"
        ).aggregate(total=Sum("payout"), count=Count("id"))
        logger.debug("B2B analytics: org=%s conversions=%s payout=%s", org.slug, agg["count"], agg["total"])
