# api/promotions/utils/instagram_api.py
import logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('utils.instagram')

IG_BASE = 'https://graph.instagram.com'

class InstagramAPI:
    def get_profile(self, ig_user_id: str, access_token: str) -> dict:
        try:
            r = requests.get(f'{IG_BASE}/{ig_user_id}',
                params={'fields':'id,username,followers_count,media_count','access_token':access_token}, timeout=10)
            return r.json()
        except Exception: return {}

    def verify_follow(self, business_ig_id: str, user_token: str) -> bool:
        """User follows the account কিনা — Instagram Graph API (business account required)।"""
        try:
            r = requests.get(f'{IG_BASE}/{business_ig_id}/followers',
                params={'access_token': user_token}, timeout=10)
            return r.status_code == 200
        except Exception: return False

    def get_media_stats(self, media_id: str, access_token: str) -> dict:
        try:
            r = requests.get(f'{IG_BASE}/{media_id}/insights',
                params={'metric':'impressions,reach,likes,comments','access_token':access_token}, timeout=10)
            data = r.json().get('data', [])
            return {item['name']: item['values'][0]['value'] for item in data}
        except Exception: return {}
