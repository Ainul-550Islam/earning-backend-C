# api/admin_panel/pixel_manager.py
"""Tracking pixel and tag management admin."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class PixelManager:
    """Manage tracking pixels, conversion tags, analytics scripts."""

    PIXEL_TYPES = {
        'facebook':  'Facebook Pixel',
        'google':    'Google Ads Tag',
        'tiktok':    'TikTok Pixel',
        'snapchat':  'Snapchat Pixel',
        'custom':    'Custom Script',
        'postback':  'Server-to-Server Postback',
    }

    @classmethod
    def add_pixel(cls, pixel_type: str, pixel_id: str, name: str,
                  placement: str = 'global', actor=None) -> Dict:
        """Add a tracking pixel to the platform."""
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            pixels_raw = SystemConfig.objects.filter(key='tracking_pixels').first()
            pixels = json.loads(pixels_raw.value) if pixels_raw else []
            pixels.append({
                'id': pixel_id, 'type': pixel_type, 'name': name,
                'placement': placement, 'is_active': True,
                'added_at': timezone.now().isoformat(),
            })
            SystemConfig.objects.update_or_create(
                key='tracking_pixels',
                defaults={'value': json.dumps(pixels), 'group': 'marketing', 'value_type': 'json'}
            )
            cache.delete('admin_panel:tracking_pixels')
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='add_pixel',
                                  changes={'type': pixel_type, 'pixel_id': pixel_id, 'name': name})
            return {'success': True, 'pixel_id': pixel_id, 'type': pixel_type}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_all_pixels(cls) -> List[Dict]:
        cached = cache.get('admin_panel:tracking_pixels')
        if cached:
            return cached
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='tracking_pixels')
            pixels = json.loads(obj.value)
            cache.set('admin_panel:tracking_pixels', pixels, 300)
            return pixels
        except Exception:
            return []

    @classmethod
    def toggle_pixel(cls, pixel_id: str, actor=None) -> bool:
        pixels = cls.get_all_pixels()
        for p in pixels:
            if p.get('id') == pixel_id:
                p['is_active'] = not p.get('is_active', True)
                break
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            SystemConfig.objects.filter(key='tracking_pixels').update(value=json.dumps(pixels))
            cache.delete('admin_panel:tracking_pixels')
            return True
        except Exception:
            return False

    @classmethod
    def generate_pixel_code(cls, pixel_type: str, pixel_id: str) -> str:
        """Generate pixel HTML/JS code for embedding."""
        templates = {
            'facebook': f"<!-- Facebook Pixel -->\n<script>\n!function(f,b,e,v,n,t,s)\n{{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?\nn.callMethod.apply(n,arguments):n.queue.push(arguments)}};}}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');\nfbq('init', '{pixel_id}');\nfbq('track', 'PageView');\n</script>",
            'google':   f"<!-- Google Tag -->\n<script async src=\"https://www.googletagmanager.com/gtag/js?id={pixel_id}\"></script>\n<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}\ngtag('js',new Date());gtag('config','{pixel_id}');\n</script>",
            'tiktok':   f"<!-- TikTok Pixel -->\n<script>!function(w,d,t){{w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];ttq.methods=[\"page\",\"track\"];ttq._i={{}};ttq._i.'{pixel_id}'=[];ttq.load('{pixel_id}');ttq.page();}}(window,document,'ttq');\n</script>",
        }
        return templates.get(pixel_type, f"<!-- Custom Pixel {pixel_id} -->")


pixel_manager = PixelManager()