# api/admin_panel/white_label.py
"""White-label configuration — logo, colors, domain, branding."""
from __future__ import annotations
import logging
from typing import Dict, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)
CACHE_KEY = 'admin_panel:white_label_config'


class WhiteLabelConfig:
    DEFAULTS = {
        'site_name':         'Earning Platform',
        'site_tagline':      'Earn money online with simple tasks',
        'primary_color':     '#4F46E5',
        'secondary_color':   '#10B981',
        'logo_url':          '',
        'favicon_url':       '',
        'support_email':     'support@example.com',
        'support_phone':     '',
        'footer_text':       '© 2024 Earning Platform. All rights reserved.',
        'currency_symbol':   '৳',
        'currency_code':     'BDT',
        'timezone':          'Asia/Dhaka',
        'app_store_url':     '',
        'play_store_url':    '',
        'social_facebook':   '',
        'social_twitter':    '',
        'social_telegram':   '',
        'min_payout':        10,
        'welcome_bonus':     0,
        'referral_rate':     5,
        'maintenance_msg':   'We are undergoing maintenance. Back soon!',
    }

    @classmethod
    def get(cls) -> Dict:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached
        try:
            from api.admin_panel.models.core import SystemSettings
            s = SystemSettings.objects.first()
            if not s:
                return cls.DEFAULTS.copy()
            config = {**cls.DEFAULTS}
            for key in cls.DEFAULTS:
                if hasattr(s, key):
                    config[key] = getattr(s, key, cls.DEFAULTS[key])
            cache.set(CACHE_KEY, config, 300)
            return config
        except Exception:
            return cls.DEFAULTS.copy()

    @classmethod
    def update(cls, updates: Dict, actor=None) -> Dict:
        allowed_keys = set(cls.DEFAULTS.keys())
        safe_updates = {k: v for k, v in updates.items() if k in allowed_keys}
        try:
            from api.admin_panel.models.core import SystemSettings
            settings = SystemSettings.load()
            for key, value in safe_updates.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            settings.save()
            cache.delete(CACHE_KEY)
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='update_white_label',
                                  changes={'updated_keys': list(safe_updates.keys())})
            return {'success': True, 'updated': list(safe_updates.keys())}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_public_config(cls) -> Dict:
        """Safe subset for public API (no admin-only fields)."""
        full = cls.get()
        public_keys = ['site_name', 'site_tagline', 'primary_color', 'secondary_color',
                       'logo_url', 'currency_symbol', 'currency_code', 'app_store_url',
                       'play_store_url', 'min_payout', 'welcome_bonus', 'referral_rate']
        return {k: full[k] for k in public_keys if k in full}

white_label = WhiteLabelConfig()