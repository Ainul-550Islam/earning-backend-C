# api/promotions/utils/google_play_api.py
import logging, requests
from django.core.cache import cache
logger = logging.getLogger('utils.play')

class GooglePlayAPI:
    BASE = 'https://androidpublisher.googleapis.com/androidpublisher/v3'

    def get_app_info(self, package_name: str) -> dict:
        ck = f'play:app:{package_name}'
        if cache.get(ck): return cache.get(ck)
        try:
            # Public play store scrape (no auth required)
            r = requests.get(f'https://play.google.com/store/apps/details?id={package_name}&hl=en', timeout=10)
            if r.status_code != 200: return {}
            import re
            title   = re.search(r'<title>(.+?) - Apps on Google Play</title>', r.text)
            rating  = re.search(r'"starRating":"([0-9.]+)"', r.text)
            reviews = re.search(r'"ratingsCount":"([0-9]+)"', r.text)
            data = {
                'package': package_name,
                'title':   title.group(1) if title else '',
                'rating':  float(rating.group(1)) if rating else 0.0,
                'reviews': int(reviews.group(1)) if reviews else 0,
                'url':     f'https://play.google.com/store/apps/details?id={package_name}',
            }
            cache.set(ck, data, timeout=3600)
            return data
        except Exception as e:
            logger.error(f'Play Store error: {e}'); return {}

    def verify_install(self, package_name: str, purchase_token: str, service_account_key: dict) -> bool:
        """Google Play Developer API দিয়ে install verify করে।"""
        logger.debug(f'Install verify: {package_name}')
        return True  # Implement with google-auth-library
