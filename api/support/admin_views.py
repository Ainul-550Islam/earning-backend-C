# api/support/admin_views.py
"""
Custom admin views for support — dashboard, bulk ops, reports.
Mount in urls.py or admin_panel urls.
"""
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

logger = logging.getLogger(__name__)


@staff_member_required
@require_GET
def admin_support_dashboard(request):
    """JSON endpoint for admin support dashboard widget."""
    try:
        from api.support.cache import get_ticket_stats
        stats = get_ticket_stats()
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f'admin_support_dashboard: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_GET
def admin_sla_report(request):
    """Admin SLA compliance report."""
    try:
        from api.support.reports import reports_service
        days   = int(request.GET.get('days', 30))
        report = reports_service.get_sla_report(days=days)
        return JsonResponse({'success': True, 'report': report})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_GET
def admin_export_tickets(request):
    """Export tickets to CSV from admin."""
    from api.support.models import SupportTicket
    from api.support.data_export import export_tickets_csv, get_export_response
    from django.utils import timezone
    from datetime import timedelta

    days = int(request.GET.get('days', 30))
    since = timezone.now() - timedelta(days=days)
    qs    = SupportTicket.objects.filter(created_at__gte=since)

    data     = export_tickets_csv(qs)
    filename = f'tickets_{timezone.now().strftime("%Y%m%d")}.csv'
    return get_export_response(data, filename)


@staff_member_required
@require_GET
def admin_health_check(request):
    """Support system health check for admin."""
    from api.support.monitoring import monitor
    status = monitor.get_health_status()
    http_status = 200 if status['status'] == 'healthy' else 503
    return JsonResponse(status, status=http_status)


@staff_member_required
@require_GET
def admin_metrics(request):
    """Real-time metrics for admin panel."""
    from api.support.monitoring import monitor
    metrics = monitor.get_metrics()
    return JsonResponse({'success': True, 'metrics': metrics})