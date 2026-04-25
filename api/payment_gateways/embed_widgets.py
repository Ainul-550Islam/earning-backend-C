# api/payment_gateways/embed_widgets.py
# Embeddable widgets for publisher sites
from django.conf import settings
import logging
logger=logging.getLogger(__name__)
BASE_URL=getattr(settings,'SITE_URL','https://yourdomain.com') if settings.configured else 'https://yourdomain.com'
CDN_URL=getattr(settings,'LOCKER_CDN_URL',f'{BASE_URL}/static/locker') if settings.configured else f'{BASE_URL}/static/locker'

class WidgetGenerator:
    def earnings_badge(self,publisher,style='compact'):
        pid=publisher.id
        return f'''<div id="pg-earnings-badge" data-publisher="{pid}" data-style="{style}"></div>
<script src="{CDN_URL}/badge.js" async></script>'''
    def offer_feed(self,publisher,limit=10,category='',country=''):
        return f'''<div id="pg-offer-feed" data-publisher="{publisher.id}" data-limit="{limit}" data-category="{category}" data-country="{country}"></div>
<script src="{CDN_URL}/feed.js" async></script>'''
    def conversion_counter(self,offer_id,style='number'):
        return f'''<span id="pg-counter" data-offer="{offer_id}" data-style="{style}">0</span>
<script src="{CDN_URL}/counter.js" async></script>'''
    def payment_button(self,amount,gateway='bkash',label='Pay Now',currency='BDT'):
        return f'''<button class="pg-pay-btn" data-amount="{amount}" data-gateway="{gateway}" data-currency="{currency}" style="background:#635BFF;color:white;padding:12px 24px;border:none;border-radius:6px;cursor:pointer;">{label}</button>
<script src="{CDN_URL}/pay.js" async></script>'''
widget_generator=WidgetGenerator()
