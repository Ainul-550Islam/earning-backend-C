# api/cms/adapters/support_ratelimit.py
"""
Adapters for api.support and api.rate_limit

  SupportAdapter   — create tickets, check ticket status, add notes from CMS
  RateLimitAdapter — check/consume rate limit tokens before expensive CMS operations
"""
import logging
from typing import Optional, Dict, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# SUPPORT ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class SupportAdapter(BaseAdapter):
    """CMS → api.support interface."""

    _system_name = 'api.support'

    @classmethod
    def _check_available(cls):
        import api.support  # noqa

    @classmethod
    def create_ticket(
        cls,
        user,
        subject: str,
        body: str,
        category: str = 'cms',
        priority: str = 'normal',
        metadata: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Create a support ticket on behalf of a user.
        Returns {'ticket_id': str, 'status': str} or None.
        """
        try:
            from api.support.services import SupportService
            ticket = SupportService.create_ticket(
                user=user,
                subject=subject,
                body=body,
                category=category,
                priority=priority,
                metadata=metadata or {},
            )
            return {'ticket_id': str(ticket.pk), 'status': ticket.status} if ticket else None
        except ImportError:
            return cls._unavailable('create_ticket', None)
        except Exception as e:
            logger.warning("[CMS→Support] create_ticket failed: %s", e)
            return None

    @classmethod
    def get_ticket(cls, ticket_id: str) -> Optional[Dict]:
        """Fetch ticket details."""
        try:
            from api.support.models import SupportTicket
            ticket = SupportTicket.objects.filter(pk=ticket_id).first()
            if not ticket:
                return None
            return {
                'ticket_id': str(ticket.pk),
                'subject': ticket.subject,
                'status': ticket.status,
                'priority': ticket.priority,
                'created_at': ticket.created_at.isoformat(),
            }
        except (ImportError, Exception):
            return None

    @classmethod
    def get_user_tickets(cls, user, status: str = '') -> List[Dict]:
        """List all tickets for a user."""
        try:
            from api.support.models import SupportTicket
            qs = SupportTicket.objects.filter(user=user).order_by('-created_at')
            if status:
                qs = qs.filter(status=status)
            return [
                {
                    'ticket_id': str(t.pk),
                    'subject': t.subject,
                    'status': t.status,
                    'priority': t.priority,
                    'created_at': t.created_at.isoformat(),
                }
                for t in qs[:50]
            ]
        except ImportError:
            return cls._unavailable('get_user_tickets', [])
        except Exception:
            return []

    @classmethod
    def add_note(cls, ticket_id: str, user, message: str, is_internal: bool = False) -> bool:
        """Add a note/reply to an existing ticket."""
        try:
            from api.support.services import SupportService
            SupportService.add_reply(
                ticket_id=ticket_id,
                user=user,
                message=message,
                is_internal=is_internal,
            )
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning("[CMS→Support] add_note failed: %s", e)
            return False

    @classmethod
    def auto_create_cms_error_ticket(cls, user, error_summary: str, context: Optional[Dict] = None) -> bool:
        """
        Automatically open a support ticket when a CMS user hits a critical error.
        Used by CMS error handlers.
        """
        ticket = cls.create_ticket(
            user=user,
            subject=f'CMS Error: {error_summary[:80]}',
            body=f'An error occurred in the CMS.\n\nSummary: {error_summary}',
            category='cms_error',
            priority='high',
            metadata=context or {},
        )
        return ticket is not None

    @classmethod
    def get_faq_articles(cls, category: str = '', query: str = '') -> List[Dict]:
        """Fetch FAQ/knowledge-base articles for CMS help widgets."""
        try:
            from api.support.models import FAQArticle
            qs = FAQArticle.objects.filter(is_published=True)
            if category:
                qs = qs.filter(category__slug=category)
            if query:
                qs = qs.filter(title__icontains=query)
            return list(qs.values('slug', 'title', 'summary', 'category__name')[:20])
        except (ImportError, Exception):
            return []


# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMIT ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class RateLimitAdapter(BaseAdapter):
    """CMS → api.rate_limit interface."""

    _system_name = 'api.rate_limit'

    @classmethod
    def _check_available(cls):
        import api.rate_limit  # noqa

    @classmethod
    def check(cls, key: str, limit: int, window_seconds: int = 60) -> bool:
        """
        Check if a rate-limit key is under its limit.
        Returns True if the action is ALLOWED, False if BLOCKED.
        Does NOT consume a token — use consume() for that.
        """
        try:
            from api.rate_limit.services import RateLimitService
            return RateLimitService.check(key=key, limit=limit, window=window_seconds)
        except ImportError:
            return True  # open if rate_limit system not installed
        except Exception as e:
            logger.debug("[CMS→RateLimit] check(%s) failed: %s", key, e)
            return True

    @classmethod
    def consume(cls, key: str, limit: int, window_seconds: int = 60) -> bool:
        """
        Consume one token from the rate limit bucket for `key`.
        Returns True if allowed and token consumed, False if blocked.
        """
        try:
            from api.rate_limit.services import RateLimitService
            return RateLimitService.consume(key=key, limit=limit, window=window_seconds)
        except ImportError:
            return True
        except Exception as e:
            logger.debug("[CMS→RateLimit] consume(%s) failed: %s", key, e)
            return True

    @classmethod
    def get_remaining(cls, key: str, limit: int, window_seconds: int = 60) -> int:
        """Return remaining tokens for a rate limit key."""
        try:
            from api.rate_limit.services import RateLimitService
            remaining = RateLimitService.get_remaining(key=key, limit=limit, window=window_seconds)
            return remaining if remaining is not None else limit
        except (ImportError, Exception):
            return limit

    # ── CMS-specific rate limit helpers ───────────────────────────────────────

    @classmethod
    def check_api_request(cls, user_id: int, endpoint: str) -> bool:
        """Check general CMS API rate limit (100 req/min per user)."""
        key = f'cms:api:{user_id}:{endpoint}'
        return cls.consume(key, limit=100, window_seconds=60)

    @classmethod
    def check_form_submission(cls, user_id: int, form_id: int) -> bool:
        """Check form submission rate limit (5 per hour per user/form)."""
        key = f'cms:form:{user_id}:{form_id}'
        return cls.consume(key, limit=5, window_seconds=3600)

    @classmethod
    def check_offer_click(cls, user_id: int) -> bool:
        """Check offer click rate limit (30 per hour per user)."""
        key = f'cms:offer_click:{user_id}'
        return cls.consume(key, limit=30, window_seconds=3600)

    @classmethod
    def check_content_create(cls, user_id: int) -> bool:
        """Check content creation rate limit (20 per hour per user)."""
        key = f'cms:content_create:{user_id}'
        return cls.consume(key, limit=20, window_seconds=3600)

    @classmethod
    def check_reward_claim(cls, user_id: int) -> bool:
        """Check reward claim rate limit (50 per day per user)."""
        key = f'cms:reward_claim:{user_id}'
        return cls.consume(key, limit=50, window_seconds=86400)

    @classmethod
    def check_postback(cls, ip: str) -> bool:
        """Check inbound postback rate limit (500 per minute per IP)."""
        key = f'cms:postback_ip:{ip}'
        return cls.consume(key, limit=500, window_seconds=60)
