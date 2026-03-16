# api/promotions/utils/youtube_api.py
import logging, requests
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('utils.youtube')

YT_API_KEY = getattr(settings, 'YOUTUBE_API_KEY', '')

class YouTubeAPI:
    BASE = 'https://www.googleapis.com/youtube/v3'

    def get_channel(self, channel_id: str) -> dict:
        ck = f'yt:channel:{channel_id}'
        if cache.get(ck): return cache.get(ck)
        try:
            r = requests.get(f'{self.BASE}/channels', params={'id': channel_id, 'part': 'statistics,snippet', 'key': YT_API_KEY}, timeout=10)
            items = r.json().get('items', [])
            if not items: return {}
            s    = items[0]['statistics']
            data = {'subscribers': int(s.get('subscriberCount',0)), 'views': int(s.get('viewCount',0)),
                    'videos': int(s.get('videoCount',0)), 'title': items[0]['snippet']['title']}
            cache.set(ck, data, timeout=3600)
            return data
        except Exception as e:
            logger.error(f'YouTube API error: {e}'); return {}

    def verify_subscription(self, channel_id: str, user_token: str) -> bool:
        """OAuth token দিয়ে subscription verify করে।"""
        try:
            r = requests.get(f'{self.BASE}/subscriptions',
                params={'part':'snippet','mySubscriptions':True,'channelId':channel_id},
                headers={'Authorization': f'Bearer {user_token}'}, timeout=10)
            return bool(r.json().get('items'))
        except Exception: return False

    def get_video_stats(self, video_id: str) -> dict:
        try:
            r = requests.get(f'{self.BASE}/videos', params={'id': video_id, 'part': 'statistics', 'key': YT_API_KEY}, timeout=10)
            items = r.json().get('items', [])
            if not items: return {}
            s = items[0]['statistics']
            return {'views': int(s.get('viewCount',0)), 'likes': int(s.get('likeCount',0)), 'comments': int(s.get('commentCount',0))}
        except Exception: return {}
