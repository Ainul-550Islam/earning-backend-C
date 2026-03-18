from core.utils import generate_random_string
import hashlib
import requests
from django.core.cache import cache


def generate_referral_code(username):
    """Generate unique referral code for user"""
    base = username[:4].upper()
    random_str = generate_random_string(4).upper()
    return f"{base}{random_str}"


def hash_device_id(device_id):
    """Hash device ID for security"""
    return hashlib.sha256(device_id.encode()).hexdigest()



def get_client_ip(request):
    """Get Real Client IP Address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get User Agent String"""
    return request.META.get('HTTP_USER_AGENT', '')


def detect_vpn(ip_address):
    """
    Detect if IP is VPN/Proxy
    Using ProxyCheck.io API (Free tier: 100 requests/day)
    """
    cache_key = f"vpn_check_{ip_address}"
    cached_result = cache.get(cache_key)
    
    if cached_result is not None:
        return cached_result
    
    try:
        response = requests.get(
            f"https://proxycheck.io/v2/{ip_address}?key=YOUR_API_KEY&vpn=1",
            timeout=5
        )
        data = response.json()
        
        is_vpn = data.get(ip_address, {}).get('proxy', 'no') == 'yes'
        
        # Cache for 24 hours
        cache.set(cache_key, is_vpn, 86400)
        
        return is_vpn
    except:
        return False


def get_location_from_ip(ip_address):
    """
    Get Location from IP Address
    Using ipapi.co (Free tier: 1000 requests/day)
    """
    cache_key = f"location_{ip_address}"
    cached_result = cache.get(cache_key)
    
    if cached_result is not None:
        return cached_result
    
    try:
        response = requests.get(f"https://ipapi.co/{ip_address}/json/", timeout=5)
        data = response.json()
        
        location = {
            'city': data.get('city'),
            'country': data.get('country_name'),
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude'),
        }
        
        # Cache for 7 days
        cache.set(cache_key, location, 604800)
        
        return location
    except:
        return {}

def check_multiple_accounts(ip_address, device_id, max_accounts=2):
    """
    Check if there are multiple accounts from same IP or Device
    Returns: (is_fraud, message)
    """
    from .models import User
    
    # Check same IP (Resilient - field may not exist in DB yet)
    try:
        ip_count = User.objects.filter(registration_ip=ip_address).count()
        if ip_count >= max_accounts:
            return True, f"Multiple accounts detected from IP: {ip_address}"
    except Exception:
        ip_count = 0
    
    # Check same device
    try:
        device_count = User.objects.filter(device_id=device_id).count()
        if device_count >= 1:
            return True, f"Account already exists for this device"
    except Exception:
        pass
    
    return False, "OK"