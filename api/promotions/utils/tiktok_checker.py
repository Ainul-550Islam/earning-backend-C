# api/promotions/utils/tiktok_checker.py
import logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('utils.tiktok')

TT_BASE = 'https://open.tiktokapis.com/v2'

class TikTokAPI:
    def __init__(self):
        self.client_key    = getattr(settings, 'TIKTOK_CLIENT_KEY', '')
        self.client_secret = getattr(settings, 'TIKTOK_CLIENT_SECRET', '')

    def get_user_info(self, access_token: str) -> dict:
        try:
            r = requests.get(f'{TT_BASE}/user/info/',
                headers={'Authorization': f'Bearer {access_token}'},
                params={'fields':'open_id,display_name,follower_count,following_count,video_count'}, timeout=10)
            return r.json().get('data', {}).get('user', {})
        except Exception as e:
            logger.error(f'TikTok user info failed: {e}'); return {}

    def verify_follow(self, creator_id: str, user_token: str) -> bool:
        try:
            r = requests.post(f'{TT_BASE}/research/user/followers/',
                headers={'Authorization': f'Bearer {user_token}'},
                json={'creator_id': creator_id, 'max_count': 1}, timeout=10)
            return r.status_code == 200
        except Exception: return False

    def get_video_stats(self, video_id: str, access_token: str) -> dict:
        try:
            r = requests.get(f'{TT_BASE}/video/query/',
                headers={'Authorization': f'Bearer {access_token}'},
                params={'fields':'view_count,like_count,comment_count,share_count','filters':f'{{"video_ids":["{video_id}"]}}'},
                timeout=10)
            items = r.json().get('data',{}).get('videos',[])
            return items[0] if items else {}
        except Exception: return {}
