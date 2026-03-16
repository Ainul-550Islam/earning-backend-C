# api/promotions/utils/facebook_graph.py
import logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('utils.facebook')

FB_APP_ID     = getattr(settings, 'FACEBOOK_APP_ID', '')
FB_APP_SECRET = getattr(settings, 'FACEBOOK_APP_SECRET', '')
FB_BASE       = 'https://graph.facebook.com/v19.0'

class FacebookGraphAPI:
    def get_page_likes(self, page_id: str, access_token: str) -> int:
        try:
            r = requests.get(f'{FB_BASE}/{page_id}', params={'fields':'fan_count','access_token':access_token}, timeout=10)
            return r.json().get('fan_count', 0)
        except Exception: return 0

    def verify_page_like(self, page_id: str, user_token: str) -> bool:
        try:
            r = requests.get(f'{FB_BASE}/me/likes/{page_id}', params={'access_token': user_token}, timeout=10)
            return 'id' in r.json()
        except Exception: return False

    def get_post_stats(self, post_id: str, access_token: str) -> dict:
        try:
            r = requests.get(f'{FB_BASE}/{post_id}',
                params={'fields':'likes.summary(true),comments.summary(true),shares','access_token':access_token}, timeout=10)
            d = r.json()
            return {'likes':d.get('likes',{}).get('summary',{}).get('total_count',0),
                    'comments':d.get('comments',{}).get('summary',{}).get('total_count',0),
                    'shares':d.get('shares',{}).get('count',0)}
        except Exception: return {}

    def verify_app_token(self, user_token: str) -> dict:
        try:
            r = requests.get(f'{FB_BASE}/debug_token',
                params={'input_token':user_token,'access_token':f'{FB_APP_ID}|{FB_APP_SECRET}'}, timeout=10)
            return r.json().get('data', {})
        except Exception: return {}
