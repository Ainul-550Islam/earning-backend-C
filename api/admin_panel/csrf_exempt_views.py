# api/admin_panel/csrf_exempt_views.py
"""CSRF exempt views for WebSocket and postback endpoints."""
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
def postback_receiver(request, token=''):
    """CSRF-exempt postback endpoint."""
    if request.method not in ('GET', 'POST'):
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    return JsonResponse({'success': True, 'received': True})

@csrf_exempt
def webhook_receiver(request, source=''):
    """CSRF-exempt inbound webhook endpoint."""
    import json
    try:
        payload = json.loads(request.body) if request.body else {}
        return JsonResponse({'success': True, 'source': source})
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)