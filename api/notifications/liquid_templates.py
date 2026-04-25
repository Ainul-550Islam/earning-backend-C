# earning_backend/api/notifications/liquid_templates.py
"""
Liquid Templates — Braze-compatible Liquid template syntax for notifications.

Supports Liquid syntax using Jinja2 (already installed in Django projects):
  Hello {{ user.first_name | default: 'Friend' }}!
  {% if user.level > 5 %}VIP offer for you!{% endif %}
  You earned {{ amount | money }} today.

Liquid filters supported:
  | upcase        → UPPERCASE
  | downcase      → lowercase
  | capitalize    → Capitalize
  | default: 'X' → fallback value
  | money         → ৳1,234.56
  | date: '%d %b' → 15 Jan
  | truncate: 50  → truncate to 50 chars
  | size          → length of string/list
  | plus: N       → add number
  | minus: N      → subtract number

Usage:
    from api.notifications.liquid_templates import liquid_renderer

    rendered = liquid_renderer.render(
        'Hello {{ user.first_name }}! Your balance is {{ balance | money }}.',
        context={'user': {'first_name': 'Rahim'}, 'balance': 500.50}
    )
    # → "Hello Rahim! Your balance is ৳500.50."
"""

import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class LiquidRenderer:
    """
    Renders Liquid-compatible templates using Jinja2.

    Provides Liquid-style syntax:
    - {{ variable }}
    - {{ variable | filter }}
    - {% if condition %}...{% endif %}
    - {% for item in list %}...{% endfor %}
    - {{ variable | default: 'fallback' }}
    """

    def __init__(self):
        self._env = None
        self._available = False
        self._init_jinja2()

    def _init_jinja2(self):
        try:
            import jinja2
            from jinja2 import Environment, select_autoescape, Undefined

            class SilentUndefined(Undefined):
                """Return empty string instead of raising UndefinedError."""
                def _fail_with_undefined_error(self, *args, **kwargs):
                    return ''
                __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
                    __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
                    __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
                    __getattr__ = __lt__ = __le__ = __gt__ = __ge__ = \
                    __int__ = __float__ = __complex__ = __pow__ = __rpow__ = \
                    _fail_with_undefined_error

            env = Environment(
                variable_start_string='{{',
                variable_end_string='}}',
                block_start_string='{%',
                block_end_string='%}',
                comment_start_string='{#',
                comment_end_string='#}',
                undefined=SilentUndefined,
                autoescape=False,  # Notifications are plain text
            )

            # Register Liquid-compatible filters
            env.filters['money'] = self._filter_money
            env.filters['upcase'] = lambda s: str(s).upper()
            env.filters['downcase'] = lambda s: str(s).lower()
            env.filters['capitalize'] = lambda s: str(s).capitalize()
            env.filters['size'] = lambda s: len(s) if hasattr(s, '__len__') else 0
            env.filters['truncate'] = lambda s, n=50: str(s)[:n] + '...' if len(str(s)) > n else str(s)
            env.filters['plus'] = lambda s, n=0: float(s or 0) + float(n)
            env.filters['minus'] = lambda s, n=0: float(s or 0) - float(n)
            env.filters['times'] = lambda s, n=1: float(s or 0) * float(n)
            env.filters['divided_by'] = lambda s, n=1: float(s or 0) / float(n) if float(n) != 0 else 0
            env.filters['round'] = lambda s, n=0: round(float(s or 0), int(n))
            env.filters['date'] = self._filter_date
            env.filters['default'] = lambda s, d='': s if s not in (None, '', False, 0) else d
            env.filters['append'] = lambda s, suffix='': str(s) + str(suffix)
            env.filters['prepend'] = lambda s, prefix='': str(prefix) + str(s)
            env.filters['replace'] = lambda s, old='', new='': str(s).replace(str(old), str(new))
            env.filters['remove'] = lambda s, sub='': str(s).replace(str(sub), '')
            env.filters['strip'] = lambda s: str(s).strip()
            env.filters['split'] = lambda s, sep=' ': str(s).split(str(sep))
            env.filters['join'] = lambda lst, sep=' ': str(sep).join(str(x) for x in lst)
            env.filters['first'] = lambda lst: lst[0] if lst else ''
            env.filters['last'] = lambda lst: lst[-1] if lst else ''
            env.filters['sort'] = lambda lst: sorted(lst) if lst else []
            env.filters['uniq'] = lambda lst: list(dict.fromkeys(lst)) if lst else []
            env.filters['bd_phone'] = self._filter_bd_phone
            env.filters['mask_phone'] = lambda s: self._mask_string(s, 3, 3)
            env.filters['mask_email'] = self._filter_mask_email

            self._env = env
            self._available = True
        except ImportError:
            logger.warning('LiquidRenderer: jinja2 not installed. Run: pip install jinja2')

    def render(self, template_str: str, context: Dict) -> str:
        """
        Render a Liquid-compatible template string.

        Args:
            template_str: Template with {{ variables }} and {% tags %}.
            context:      Dict of variables available in the template.

        Returns:
            Rendered string. Returns template_str unchanged on error.
        """
        if not template_str:
            return ''

        # Fall back to simple {variable} rendering if Jinja2 not available
        if not self._available:
            return self._simple_render(template_str, context)

        try:
            template = self._env.from_string(template_str)
            # Flatten nested dicts for easy access: {'user': {'name': 'X'}} → user.name works
            flat_context = self._prepare_context(context)
            return template.render(**flat_context)
        except Exception as exc:
            logger.debug(f'LiquidRenderer.render: {exc}')
            return self._simple_render(template_str, context)

    def render_notification(self, notification_template, context: Dict) -> Tuple[str, str]:
        """
        Render a NotificationTemplate's title and message.

        Returns:
            (rendered_title, rendered_message) tuple.
        """
        user = context.get('user')
        user_context = {}
        if user:
            user_context = {
                'first_name': getattr(user, 'first_name', '') or getattr(user, 'username', ''),
                'last_name': getattr(user, 'last_name', ''),
                'username': getattr(user, 'username', ''),
                'email': getattr(user, 'email', ''),
            }
            # Add profile data if available
            profile = getattr(user, 'profile', None)
            if profile:
                user_context.update({
                    'level': getattr(profile, 'level', 1),
                    'tier': getattr(profile, 'tier', 'basic'),
                    'total_earned': getattr(profile, 'total_earned', 0),
                    'language': getattr(profile, 'language', 'en'),
                })

        full_context = {**context, 'user': user_context}

        # Use BN template if user language is BN and BN template exists
        language = user_context.get('language', 'en')
        if language == 'bn':
            title_tpl = getattr(notification_template, 'title_bn', '') or getattr(notification_template, 'title_en', '')
            msg_tpl = getattr(notification_template, 'message_bn', '') or getattr(notification_template, 'message_en', '')
        else:
            title_tpl = getattr(notification_template, 'title_en', '')
            msg_tpl = getattr(notification_template, 'message_en', '')

        title = self.render(title_tpl, full_context)
        message = self.render(msg_tpl, full_context)
        return title, message

    def validate_template(self, template_str: str) -> Tuple[bool, str]:
        """Validate a template for syntax errors."""
        if not self._available:
            return True, ''
        try:
            self._env.from_string(template_str)
            return True, ''
        except Exception as exc:
            return False, str(exc)

    def get_template_variables(self, template_str: str) -> list:
        """Extract all {{ variable }} names from a template."""
        return list(set(re.findall(r'\{\{\s*(\w+)', template_str)))

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_money(value, currency='৳') -> str:
        try:
            amount = float(value or 0)
            if amount == int(amount):
                return f'{currency}{int(amount):,}'
            return f'{currency}{amount:,.2f}'
        except (TypeError, ValueError):
            return f'{currency}0'

    @staticmethod
    def _filter_date(value, fmt='%d %b %Y') -> str:
        try:
            from django.utils import timezone
            if hasattr(value, 'strftime'):
                return value.strftime(fmt)
            from datetime import datetime
            dt = datetime.fromisoformat(str(value))
            return dt.strftime(fmt)
        except Exception:
            return str(value)

    @staticmethod
    def _filter_bd_phone(value) -> str:
        """Format as BD phone: 01712345678"""
        from api.notifications.helpers import normalize_bd_phone
        return normalize_bd_phone(str(value))

    @staticmethod
    def _mask_string(s: str, show_start: int = 3, show_end: int = 3) -> str:
        s = str(s)
        if len(s) <= show_start + show_end:
            return '*' * len(s)
        return s[:show_start] + '*' * (len(s) - show_start - show_end) + s[-show_end:]

    @staticmethod
    def _filter_mask_email(email: str) -> str:
        if '@' not in str(email):
            return '****'
        local, domain = str(email).split('@', 1)
        visible = min(2, len(local))
        return local[:visible] + '*' * max(0, len(local) - visible) + '@' + domain

    @staticmethod
    def _prepare_context(context: Dict) -> Dict:
        """Prepare context for Jinja2 rendering."""
        prepared = {}
        for key, value in context.items():
            if hasattr(value, '__dict__') and not isinstance(value, type):
                # Convert model instances to dicts
                prepared[key] = {
                    k: v for k, v in vars(value).items()
                    if not k.startswith('_')
                }
            else:
                prepared[key] = value
        return prepared

    @staticmethod
    def _simple_render(template_str: str, context: Dict) -> str:
        """Fallback simple {variable} rendering without Jinja2."""
        result = template_str
        flat = {}
        for key, value in context.items():
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    flat[f'{key}.{subkey}'] = subval
                    flat[f'{key}_{subkey}'] = subval
            flat[key] = value

        def replace_var(match):
            var_name = match.group(1).strip().split('|')[0].strip()
            return str(flat.get(var_name, ''))

        return re.sub(r'\{\{([^}]+)\}\}', replace_var, result)


# Singleton
liquid_renderer = LiquidRenderer()
