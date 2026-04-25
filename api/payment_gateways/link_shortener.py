# api/payment_gateways/link_shortener.py
# Short link generator for tracking links
import secrets,string,logging
from django.core.cache import cache
logger=logging.getLogger(__name__)

class LinkShortener:
    BASE_URL=None
    CHARS=string.ascii_letters+string.digits
    def __init__(self):
        from django.conf import settings
        self.BASE_URL=getattr(settings,'SITE_URL','https://yourdomain.com')
    def shorten(self,url,publisher_id=None,offer_id=None):
        code=self._generate_code()
        data={'url':url,'publisher_id':publisher_id,'offer_id':offer_id,'clicks':0}
        cache.set(f'short:{code}',data,86400*365)
        return {'code':code,'short_url':f'{self.BASE_URL}/go/{code}','original_url':url}
    def resolve(self,code):
        data=cache.get(f'short:{code}')
        if not data: return None
        data['clicks']+=1
        cache.set(f'short:{code}',data,86400*365)
        return data
    def get_stats(self,code):
        return cache.get(f'short:{code}',{})
    def _generate_code(self,length=8):
        while True:
            code=''.join(secrets.choice(self.CHARS) for _ in range(length))
            if not cache.get(f'short:{code}'): return code
link_shortener=LinkShortener()
