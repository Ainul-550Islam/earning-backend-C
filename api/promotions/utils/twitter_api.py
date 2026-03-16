# api/promotions/utils/twitter_api.py
import logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('utils.twitter')

TWITTER_BEARER = getattr(settings, 'TWITTER_BEARER_TOKEN', '')
TW_BASE        = 'https://api.twitter.com/2'

class TwitterAPI:
    HEADERS = {'Authorization': f'Bearer {TWITTER_BEARER}'}

    def get_user(self, username: str) -> dict:
        ck = f'tw:user:{username}'
        if cache.get(ck): return cache.get(ck)
        try:
            r = requests.get(f'{TW_BASE}/users/by/username/{username}',
                params={'user.fields':'public_metrics,description'},
                headers=self.HEADERS, timeout=10)
            data = r.json().get('data', {})
            cache.set(ck, data, timeout=3600)
            return data
        except Exception as e:
            logger.error(f'Twitter user failed: {e}'); return {}

    def verify_follow(self, target_user_id: str, user_id: str) -> bool:
        try:
            r = requests.get(f'{TW_BASE}/users/{user_id}/following',
                params={'max_results': 1000}, headers=self.HEADERS, timeout=10)
            following = [u['id'] for u in r.json().get('data', [])]
            return target_user_id in following
        except Exception: return False

    def get_tweet_stats(self, tweet_id: str) -> dict:
        try:
            r = requests.get(f'{TW_BASE}/tweets/{tweet_id}',
                params={'tweet.fields':'public_metrics'}, headers=self.HEADERS, timeout=10)
            return r.json().get('data', {}).get('public_metrics', {})
        except Exception: return {}
