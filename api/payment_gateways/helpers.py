# api/payment_gateways/helpers.py
# Utility helper functions — imports and re-exports all helpers
import hashlib, hmac, time, uuid, secrets, re, json, logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.core.cache import cache
logger = logging.getLogger(__name__)

BD_OPERATORS = {'017':'Grameenphone','013':'Grameenphone','018':'Robi','016':'Airtel','019':'Banglalink','014':'Banglalink','015':'Teletalk','011':'Teletalk'}
BD_BKASH_ELIGIBLE = {'017','013','018','016','019','014'}
BD_NAGAD_ELIGIBLE = {'017','013','018','016','019','014','015'}
CURRENCY_SYMBOLS = {'BDT':'৳','USD':'$','EUR':'€','GBP':'£','AUD':'A$','CAD':'C$','SGD':'S$','JPY':'¥','INR':'₹','USDT':'₮','USDC':'USDC','BTC':'₿','ETH':'Ξ'}
CRYPTO_CURRENCIES = {'BTC','ETH','LTC','BCH','USDT','USDC'}

def generate_reference_id(prefix,gateway='',length=8):
    gw=gateway.upper()[:4].ljust(4,'X') if gateway else 'SYS'
    ts=str(int(time.time()*1000))[-10:]
    rnd=secrets.token_hex(length//2).upper()
    return f'{prefix}-{gw}-{ts}-{rnd}'

def generate_click_id(): return uuid.uuid4().hex
def generate_conversion_id(): return f'conv_{uuid.uuid4().hex[:20]}'
def generate_api_key(prefix='pk'): return f'{prefix}_test_{secrets.token_urlsafe(32)}'

def format_amount(amount,currency='USD'):
    symbol=CURRENCY_SYMBOLS.get(currency.upper(),currency+' ')
    precision=8 if currency.upper() in CRYPTO_CURRENCIES else (0 if currency.upper() in {'JPY','KRW'} else 2)
    return f'{symbol}{float(Decimal(str(amount))):,.{precision}f}'

def normalize_amount(value,precision=2):
    try: return Decimal(str(value)).quantize(Decimal('0.'+'0'*precision),rounding=ROUND_HALF_UP)
    except: return Decimal('0')

def calculate_percentage(part,total,decimals=2):
    return round(float(part/total*100),decimals) if total else 0.0

def apply_fee(amount,fee_percent):
    fee=(amount*fee_percent/100).quantize(Decimal('0.01'))
    return fee, amount-fee

def normalize_bd_phone(phone):
    clean=re.sub(r'[\s\-\(\)\.+]','',str(phone))
    if clean.startswith('880') and len(clean)==13: clean='0'+clean[3:]
    return clean if re.match(r'^01[3-9]\d{8}$',clean) else ''

def get_bd_operator(phone): return BD_OPERATORS.get(normalize_bd_phone(phone)[:3],'Unknown')
def is_bkash_eligible(phone): n=normalize_bd_phone(phone); return bool(n) and n[:3] in BD_BKASH_ELIGIBLE
def is_nagad_eligible(phone): n=normalize_bd_phone(phone); return bool(n) and n[:3] in BD_NAGAD_ELIGIBLE
def mask_account_number(account,visible=4): return '*'*(len(account)-visible)+account[-visible:] if account and len(account)>visible else '****'
def mask_phone(phone): return phone[:4]+'****'+phone[-3:] if phone and len(phone)>=7 else '****'
def mask_email(email): local,domain=email.split('@',1) if '@' in email else (email,''); return (local[:2]+'**@'+domain) if local else '****'

def hmac_sha256(secret,message):
    if isinstance(message,str): message=message.encode()
    return hmac.new(secret.encode(),message,hashlib.sha256).hexdigest()

def verify_signature(secret,message,received,algo='sha256'):
    expected=hmac_sha256(secret,message) if algo=='sha256' else hmac.new(secret.encode(),(message.encode() if isinstance(message,str) else message),hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected.lower(),received.lower().replace('sha256=','').replace('sha512=',''))

def get_client_ip(request):
    return request.META.get('HTTP_CF_CONNECTING_IP') or (request.META.get('HTTP_X_FORWARDED_FOR','').split(',')[0].strip()) or request.META.get('REMOTE_ADDR','')

def detect_device_type(ua):
    ua=ua.lower()
    if any(p in ua for p in ('bot','crawler','spider','curl','wget','python-requests')): return 'bot'
    if any(p in ua for p in ('ipad','tablet','kindle')): return 'tablet'
    if any(p in ua for p in ('iphone','android','mobile','mobi')): return 'mobile'
    return 'desktop'

def get_country_from_request(request): return request.META.get('HTTP_CF_IPCOUNTRY','').upper() or request.META.get('HTTP_X_COUNTRY_CODE','').upper()

def safe_json_loads(data,default=None):
    try:
        if isinstance(data,bytes): data=data.decode('utf-8',errors='replace')
        return json.loads(data)
    except: return default if default is not None else {}

def safe_json_dumps(data,indent=None):
    class E(json.JSONEncoder):
        def default(self,o):
            if isinstance(o,Decimal): return float(o)
            if isinstance(o,(datetime,date)): return o.isoformat()
            return super().default(o)
    try: return json.dumps(data,cls=E,indent=indent,ensure_ascii=False)
    except: return '{}'

def get_date_range(period):
    today=timezone.localtime().date()
    if period=='today': return today,today
    if period=='yesterday': y=today-timedelta(days=1); return y,y
    if period=='this_week': return today-timedelta(days=today.weekday()),today
    if period=='this_month': return today.replace(day=1),today
    if period=='last_month': e=today.replace(day=1)-timedelta(days=1); return e.replace(day=1),e
    if period.startswith('last_'):
        try: return today-timedelta(days=int(period.split('_')[1])),today
        except: pass
    return today-timedelta(days=30),today

def format_datetime_bd(dt):
    if not dt: return '—'
    local=timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return local.strftime('%d %b %Y, %I:%M %p')

def is_gateway_available(name):
    try:
        from api.payment_gateways.models.core import PaymentGateway
        gw=PaymentGateway.objects.get(name=name)
        return gw.status=='active' and gw.health_status!='down'
    except: return False

def build_success_response(data=None,message='',status_code=200): return {'success':True,'message':message,'data':data or {},'status_code':status_code}
def build_error_response(message,errors=None,status_code=400): return {'success':False,'message':message,'errors':errors or [],'status_code':status_code}

def get_or_set_cache(key,func,ttl=300):
    v=cache.get(key)
    if v is None:
        v=func()
        if v is not None: cache.set(key,v,ttl)
    return v

def calculate_gateway_fee(amount,gateway):
    from api.payment_gateways.logic import calculate_fee
    fee=calculate_fee(amount,gateway); return fee,amount-fee

def paginate_queryset(queryset,page=1,page_size=25):
    page=max(1,page); page_size=min(max(1,page_size),200)
    total=queryset.count(); offset=(page-1)*page_size; items=list(queryset[offset:offset+page_size])
    pages=(total+page_size-1)//page_size
    return {'items':items,'total':total,'page':page,'pages':pages,'page_size':page_size,'has_next':page<pages,'has_prev':page>1}
