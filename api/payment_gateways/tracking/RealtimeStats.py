# api/payment_gateways/tracking/RealtimeStats.py
# Server-Sent Events (SSE) for real-time publisher stats

from django.http import StreamingHttpResponse
from django.utils import timezone
from datetime import timedelta
import json, time


def realtime_stats_stream(request):
    """
    SSE endpoint for real-time publisher stats.
    Connect from frontend: const es = new EventSource('/api/payment/tracking/stats/live/');
    Pushes stats update every 5 seconds.
    """
    user = request.user
    if not user.is_authenticated:
        from django.http import HttpResponse
        return HttpResponse('Unauthorized', status=401)

    def generate():
        while True:
            try:
                from api.payment_gateways.tracking.models import Conversion, Click
                from django.db.models import Sum, Count

                today = timezone.now().date()

                # Today's stats
                today_stats = Conversion.objects.filter(
                    publisher=user, status='approved', created_at__date=today
                ).aggregate(revenue=Sum('payout'), count=Count('id'))

                # Last hour clicks
                since_hour = timezone.now() - timedelta(hours=1)
                recent_clicks = Click.objects.filter(
                    publisher=user, created_at__gte=since_hour, is_bot=False
                ).count()

                # Balance
                balance = float(getattr(user, 'balance', 0) or 0)

                data = {
                    'timestamp':       timezone.now().isoformat(),
                    'today_earnings':  float(today_stats.get('revenue') or 0),
                    'today_conversions': today_stats.get('count') or 0,
                    'last_hour_clicks': recent_clicks,
                    'balance':         balance,
                }

                yield f'data: {json.dumps(data)}\n\n'
            except Exception:
                yield f'data: {json.dumps({"error": "stats unavailable"})}\n\n'

            time.sleep(5)

    response = StreamingHttpResponse(generate(), content_type='text/event-stream')
    response['Cache-Control']    = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
