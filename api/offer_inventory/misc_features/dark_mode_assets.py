# api/offer_inventory/misc_features/dark_mode_assets.py
"""
Dark Mode Asset Manager.
Manages light/dark/cyberpunk UI themes.
Returns CSS variables and theme config for frontend rendering.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

THEMES = {
    'light': {
        'background'  : '#FFFFFF',
        'surface'     : '#F8F9FA',
        'primary'     : '#6C63FF',
        'secondary'   : '#FF6584',
        'text'        : '#212529',
        'text_muted'  : '#6C757D',
        'border'      : '#DEE2E6',
        'success'     : '#28A745',
        'warning'     : '#FFC107',
        'danger'      : '#DC3545',
        'card_bg'     : '#FFFFFF',
        'shadow'      : 'rgba(0,0,0,0.1)',
        'navbar_bg'   : '#FFFFFF',
        'sidebar_bg'  : '#F8F9FA',
    },
    'dark': {
        'background'  : '#0D1117',
        'surface'     : '#161B22',
        'primary'     : '#7C74FF',
        'secondary'   : '#FF7A95',
        'text'        : '#E6EDF3',
        'text_muted'  : '#8B949E',
        'border'      : '#30363D',
        'success'     : '#3FB950',
        'warning'     : '#D29922',
        'danger'      : '#F85149',
        'card_bg'     : '#161B22',
        'shadow'      : 'rgba(0,0,0,0.5)',
        'navbar_bg'   : '#010409',
        'sidebar_bg'  : '#0D1117',
    },
    'cyberpunk': {
        'background'  : '#0A0A0F',
        'surface'     : '#12121F',
        'primary'     : '#00FFB3',
        'secondary'   : '#FF00A0',
        'text'        : '#E0E0FF',
        'text_muted'  : '#8080A0',
        'border'      : '#2A2A4A',
        'success'     : '#00FF88',
        'warning'     : '#FFE000',
        'danger'      : '#FF003C',
        'card_bg'     : '#12121F',
        'shadow'      : 'rgba(0,255,179,0.1)',
        'navbar_bg'   : '#050508',
        'sidebar_bg'  : '#0A0A0F',
    },
    'solarized': {
        'background'  : '#FDF6E3',
        'surface'     : '#EEE8D5',
        'primary'     : '#268BD2',
        'secondary'   : '#D33682',
        'text'        : '#657B83',
        'text_muted'  : '#93A1A1',
        'border'      : '#D3CBB8',
        'success'     : '#859900',
        'warning'     : '#B58900',
        'danger'      : '#DC322F',
        'card_bg'     : '#FDF6E3',
        'shadow'      : 'rgba(0,0,0,0.08)',
        'navbar_bg'   : '#EEE8D5',
        'sidebar_bg'  : '#EEE8D5',
    },
}

DEFAULT_THEME = 'dark'


class DarkModeAssetManager:
    """UI theme management for dark/light mode support."""

    @classmethod
    def get_theme(cls, theme_name: str = DEFAULT_THEME) -> dict:
        """Get theme color variables."""
        return THEMES.get(theme_name, THEMES[DEFAULT_THEME])

    @classmethod
    def get_css_variables(cls, theme_name: str = DEFAULT_THEME) -> str:
        """Generate CSS :root variables string."""
        theme = cls.get_theme(theme_name)
        lines = [':root {']
        for key, value in theme.items():
            css_var = f'--oi-{key.replace("_", "-")}'
            lines.append(f'  {css_var}: {value};')
        lines.append('}')
        return '\n'.join(lines)

    @classmethod
    def get_all_themes(cls) -> dict:
        """Return all available theme names and their primary colors."""
        return {
            name: {
                'primary'    : data['primary'],
                'background' : data['background'],
                'text'       : data['text'],
            }
            for name, data in THEMES.items()
        }

    @classmethod
    def get_user_theme(cls, user) -> str:
        """Get user's saved theme preference."""
        cache_key = f'user_theme:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.offer_inventory.models import UserProfile
            profile = UserProfile.objects.get(user=user)
            prefs   = profile.notification_prefs or {}
            theme   = prefs.get('theme', DEFAULT_THEME)
            cache.set(cache_key, theme, 3600)
            return theme
        except Exception:
            return DEFAULT_THEME

    @classmethod
    def set_user_theme(cls, user, theme: str) -> bool:
        """Save user's theme preference."""
        if theme not in THEMES:
            raise ValueError(f'Unknown theme: {theme}. Available: {list(THEMES.keys())}')
        from api.offer_inventory.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        prefs      = profile.notification_prefs or {}
        prefs['theme'] = theme
        UserProfile.objects.filter(user=user).update(notification_prefs=prefs)
        cache.set(f'user_theme:{user.id}', theme, 3600)
        return True

    @classmethod
    def get_themed_response(cls, user=None, theme_name: str = None) -> dict:
        """Full themed config for frontend initial load."""
        theme = theme_name or (cls.get_user_theme(user) if user else DEFAULT_THEME)
        return {
            'theme_name'    : theme,
            'colors'        : cls.get_theme(theme),
            'css_variables' : cls.get_css_variables(theme),
            'available'     : list(THEMES.keys()),
        }
