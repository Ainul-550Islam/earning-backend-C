# api/payment_gateways/middleware.py

from django.http import HttpResponseForbidden
from django.conf import settings
import ipaddress

class WebhookIPWhitelistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/payments/webhooks/'):
            # Extract gateway from path
            path_parts = request.path.split('/')
            gateway = path_parts[-2] if len(path_parts) > 1 else None
            
            if gateway in ['bkash', 'stripe', 'nagad']:
                allowed_ips = getattr(settings, 'WEBHOOK_ALLOWED_IPS', {}).get(gateway, [])
                
                if allowed_ips:
                    client_ip = self.get_client_ip(request)
                    if not self.is_ip_allowed(client_ip, allowed_ips):
                        return HttpResponseForbidden('IP not allowed')
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_ip_allowed(self, client_ip, allowed_ranges):
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            for ip_range in allowed_ranges:
                if '/' in ip_range:
                    if client_ip_obj in ipaddress.ip_network(ip_range):
                        return True
                else:
                    if str(client_ip_obj) == ip_range:
                        return True
            return False
        except ValueError:
            return False