# api/cms/adapters/platform.py
"""
Adapters for platform-level systems:
  api.tasks, api.cache, api.audit_logs, api.subscription, api.ai_engine,
  api.auto_mod, api.version_control, api.localization
"""
import logging
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# TASKS ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class TasksAdapter(BaseAdapter):
    """CMS → api.tasks — schedule background tasks."""

    _system_name = 'api.tasks'

    @classmethod
    def _check_available(cls):
        import api.tasks  # noqa

    @classmethod
    def schedule(cls, task_name: str, args: list = None, kwargs: dict = None,
                 countdown: int = 0, eta=None) -> Optional[str]:
        """Schedule a Celery task. Returns task_id or None."""
        try:
            from api.tasks.registry import get_task
            task = get_task(task_name)
            if task:
                result = task.apply_async(args=args or [], kwargs=kwargs or {},
                                          countdown=countdown, eta=eta)
                return result.id
            return None
        except ImportError:
            return None
        except Exception as e:
            logger.warning("[CMS→Tasks] schedule(%s) failed: %s", task_name, e)
            return None

    @classmethod
    def schedule_cms_publish(cls, content_type: str, content_id: int, publish_at) -> Optional[str]:
        """Schedule CMS content publication at a specific time."""
        return cls.schedule(
            'api.cms.tasks.publish_content',
            kwargs={'content_type': content_type, 'content_id': content_id},
            eta=publish_at,
        )


# ══════════════════════════════════════════════════════════════════════════════
# CACHE ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class CacheAdapter(BaseAdapter):
    """CMS → api.cache — distributed cache operations."""

    _system_name = 'api.cache'

    @classmethod
    def _check_available(cls):
        import api.cache  # noqa

    @classmethod
    def get(cls, key: str) -> Any:
        try:
            from api.cache.services import CacheService
            return CacheService.get(key)
        except ImportError:
            from django.core.cache import cache
            return cache.get(key)
        except Exception:
            return None

    @classmethod
    def set(cls, key: str, value: Any, timeout: int = 300) -> bool:
        try:
            from api.cache.services import CacheService
            CacheService.set(key, value, timeout=timeout)
            return True
        except ImportError:
            from django.core.cache import cache
            cache.set(key, value, timeout)
            return True
        except Exception:
            return False

    @classmethod
    def delete(cls, key: str) -> bool:
        try:
            from api.cache.services import CacheService
            CacheService.delete(key)
            return True
        except ImportError:
            from django.core.cache import cache
            cache.delete(key)
            return True
        except Exception:
            return False

    @classmethod
    def invalidate_cms_content(cls, content_type: str, content_id: str) -> bool:
        """Invalidate all CMS cache keys for a given piece of content."""
        keys = [
            f"cms:{content_type}:{content_id}",
            f"cms:{content_type}:{content_id}:list",
            f"cms:public:{content_type}:{content_id}",
        ]
        for key in keys:
            cls.delete(key)
        return True


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOGS ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class AuditAdapter(BaseAdapter):
    """CMS → api.audit_logs — immutable audit trail."""

    _system_name = 'api.audit_logs'

    @classmethod
    def _check_available(cls):
        import api.audit_logs  # noqa

    @classmethod
    def log(cls, action: str, user=None, resource_type: str = '',
            resource_id: str = '', data: Optional[Dict] = None, ip: str = '') -> bool:
        try:
            from api.audit_logs.services import AuditLogService
            AuditLogService.log(
                action=action, user=user, resource_type=resource_type,
                resource_id=str(resource_id), data=data or {}, ip=ip,
            )
            return True
        except ImportError:
            logger.debug("[CMS→Audit] %s: %s %s (audit_logs unavailable)", action, resource_type, resource_id)
            return False
        except Exception as e:
            logger.warning("[CMS→Audit] log failed: %s", e)
            return False

    @classmethod
    def content_created(cls, user, content_type: str, content_id: str, ip: str = '') -> bool:
        return cls.log('cms.content.created', user, content_type, content_id, ip=ip)

    @classmethod
    def content_updated(cls, user, content_type: str, content_id: str, changes: Dict = None, ip: str = '') -> bool:
        return cls.log('cms.content.updated', user, content_type, content_id, data={'changes': changes or {}}, ip=ip)

    @classmethod
    def content_deleted(cls, user, content_type: str, content_id: str, ip: str = '') -> bool:
        return cls.log('cms.content.deleted', user, content_type, content_id, ip=ip)

    @classmethod
    def content_published(cls, user, content_type: str, content_id: str) -> bool:
        return cls.log('cms.content.published', user, content_type, content_id)

    @classmethod
    def permission_changed(cls, user, target_id: str, permission: str) -> bool:
        return cls.log('cms.permission.changed', user, 'permission', target_id, {'permission': permission})

    @classmethod
    def reward_issued(cls, user, amount: float, source: str) -> bool:
        return cls.log('cms.reward.issued', user, 'reward', source, {'amount': amount})


# ══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class SubscriptionAdapter(BaseAdapter):
    """CMS → api.subscription — check plan/feature gating."""

    _system_name = 'api.subscription'

    @classmethod
    def _check_available(cls):
        import api.subscription  # noqa

    @classmethod
    def get_plan(cls, user) -> str:
        """Return user's current subscription plan slug."""
        try:
            from api.subscription.models import UserSubscription
            sub = UserSubscription.objects.filter(user=user, is_active=True).first()
            return getattr(sub, 'plan_slug', 'free') if sub else 'free'
        except ImportError:
            return 'free'
        except Exception:
            return 'free'

    @classmethod
    def has_feature(cls, user, feature: str) -> bool:
        """Check if the user's subscription plan includes a feature."""
        try:
            from api.subscription.services import SubscriptionService
            return SubscriptionService.has_feature(user=user, feature=feature)
        except ImportError:
            return True  # open if subscription system not installed
        except Exception:
            return False

    @classmethod
    def can_access_premium_content(cls, user) -> bool:
        return cls.has_feature(user, 'premium_content')

    @classmethod
    def can_access_advanced_analytics(cls, user) -> bool:
        return cls.has_feature(user, 'advanced_analytics')


# ══════════════════════════════════════════════════════════════════════════════
# AI ENGINE ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class AIAdapter(BaseAdapter):
    """CMS → api.ai_engine — AI-powered features."""

    _system_name = 'api.ai_engine'

    @classmethod
    def _check_available(cls):
        import api.ai_engine  # noqa

    @classmethod
    def generate_content(cls, prompt: str, max_tokens: int = 500, context: Optional[Dict] = None) -> str:
        """Generate AI content."""
        try:
            from api.ai_engine.services import AIService
            return AIService.generate(prompt=prompt, max_tokens=max_tokens, context=context or {})
        except ImportError:
            return ''
        except Exception as e:
            logger.warning("[CMS→AI] generate_content failed: %s", e)
            return ''

    @classmethod
    def suggest_tags(cls, content: str) -> List[str]:
        """AI-suggested tags for a piece of content."""
        try:
            from api.ai_engine.services import AIService
            return AIService.suggest_tags(content=content) or []
        except (ImportError, Exception):
            return []

    @classmethod
    def moderate_content(cls, content: str) -> Dict:
        """
        AI content moderation.
        Returns {'safe': bool, 'flags': list, 'confidence': float}
        """
        try:
            from api.ai_engine.services import AIService
            return AIService.moderate(content=content) or {'safe': True, 'flags': [], 'confidence': 1.0}
        except ImportError:
            return {'safe': True, 'flags': [], 'confidence': 1.0}
        except Exception:
            return {'safe': True, 'flags': [], 'confidence': 0.0}

    @classmethod
    def generate_seo_meta(cls, title: str, content: str) -> Dict:
        """Generate SEO meta description and keywords from content."""
        try:
            from api.ai_engine.services import AIService
            return AIService.generate_seo(title=title, content=content) or {}
        except (ImportError, Exception):
            return {}


# ══════════════════════════════════════════════════════════════════════════════
# AUTO MODERATION ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class AutoModAdapter(BaseAdapter):
    """CMS → api.auto_mod — automated content moderation."""

    _system_name = 'api.auto_mod'

    @classmethod
    def _check_available(cls):
        import api.auto_mod  # noqa

    @classmethod
    def check(cls, content: str, content_type: str = 'text') -> Dict:
        """
        Auto-moderate content.
        Returns {'approved': bool, 'action': str, 'reason': str}
        """
        try:
            from api.auto_mod.services import AutoModService
            return AutoModService.check(content=content, content_type=content_type) or {'approved': True}
        except ImportError:
            return {'approved': True, 'action': 'approve', 'reason': 'auto_mod_unavailable'}
        except Exception as e:
            logger.warning("[CMS→AutoMod] check failed: %s", e)
            return {'approved': True, 'action': 'approve', 'reason': 'error'}

    @classmethod
    def check_comment(cls, text: str) -> bool:
        result = cls.check(text, 'comment')
        return result.get('approved', True)

    @classmethod
    def check_user_content(cls, content: str) -> bool:
        result = cls.check(content, 'user_content')
        return result.get('approved', True)


# ══════════════════════════════════════════════════════════════════════════════
# LOCALIZATION ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class LocalizationAdapter(BaseAdapter):
    """CMS → api.localization — i18n content and locale resolution."""

    _system_name = 'api.localization'

    @classmethod
    def _check_available(cls):
        import api.localization  # noqa

    @classmethod
    def get_locale(cls, user=None, request=None) -> str:
        """Resolve the best locale for a user/request."""
        try:
            from api.localization.services import LocalizationService
            return LocalizationService.get_locale(user=user, request=request) or 'en'
        except ImportError:
            return getattr(user, 'locale', 'en') if user else 'en'
        except Exception:
            return 'en'

    @classmethod
    def translate(cls, key: str, locale: str = 'en', fallback: str = '') -> str:
        """Look up a translation key."""
        try:
            from api.localization.services import LocalizationService
            return LocalizationService.translate(key=key, locale=locale) or fallback
        except (ImportError, Exception):
            return fallback

    @classmethod
    def get_supported_locales(cls) -> List[str]:
        try:
            from api.localization.models import Locale
            return list(Locale.objects.filter(is_active=True).values_list('code', flat=True))
        except (ImportError, Exception):
            return ['en']


# ══════════════════════════════════════════════════════════════════════════════
# VERSION CONTROL ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class VersionControlAdapter(BaseAdapter):
    """CMS → api.version_control — content versioning."""

    _system_name = 'api.version_control'

    @classmethod
    def _check_available(cls):
        import api.version_control  # noqa

    @classmethod
    def create_version(cls, content_type: str, content_id: int, data: Dict, user=None) -> Optional[str]:
        """Snapshot current content state. Returns version_id or None."""
        try:
            from api.version_control.services import VersionService
            version = VersionService.snapshot(
                content_type=content_type, content_id=content_id,
                data=data, user=user,
            )
            return str(version.pk) if version else None
        except ImportError:
            return None
        except Exception as e:
            logger.warning("[CMS→VersionControl] create_version failed: %s", e)
            return None

    @classmethod
    def restore_version(cls, version_id: str) -> Optional[Dict]:
        """Restore a content version. Returns the restored data dict."""
        try:
            from api.version_control.services import VersionService
            return VersionService.restore(version_id=version_id)
        except (ImportError, Exception):
            return None

    @classmethod
    def list_versions(cls, content_type: str, content_id: int) -> List[Dict]:
        try:
            from api.version_control.services import VersionService
            return VersionService.list_versions(content_type=content_type, content_id=content_id) or []
        except (ImportError, Exception):
            return []
