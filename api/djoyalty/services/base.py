# api/djoyalty/services/base.py
"""
DjoyaltyBaseService — Abstract base class for all Djoyalty service classes।

DRY FIX: Every service file repeated the same 3 patterns:
    1. logger = logging.getLogger(__name__)
    2. return {'success': False, 'error': str(e)}
    3. logger.error('SomeName.method: %s', e)

With 59 service files, this was ~177 duplicate lines of boilerplate।

All new services SHOULD inherit DjoyaltyBaseService।
Existing services CAN keep their standalone logger — backward compatible।

Usage:
    class MyService(DjoyaltyBaseService):
        @classmethod
        def do_thing(cls, customer):
            try:
                result = ...
                return cls._ok(data=result)
            except Exception as e:
                return cls._err_exc(e)
"""
import logging
from typing import Any, Dict, Optional
from ..service_result import ServiceResult


class DjoyaltyBaseService:
    """
    Base class for all Djoyalty service classes।
    Provides: structured logging, ServiceResult helpers, common error patterns।

    All methods are classmethods — services are stateless utility classes,
    not instances।  Never call DjoyaltyBaseService() directly।
    """

    # ── Logger — automatically named after the concrete subclass ──────────────
    # Subclasses get their own logger: logging.getLogger('api.djoyalty.services.CashoutService')
    # This means log lines are attributable without repeating getLogger(__name__) in every file।

    @classmethod
    def _logger(cls) -> logging.Logger:
        return logging.getLogger(
            f'api.djoyalty.services.{cls.__name__}'
        )

    # ── Logging shorthand ──────────────────────────────────────────────────────

    @classmethod
    def _log(cls, msg: str, *args: Any) -> None:
        """Info log — replaces: logger.info('ClassName.method: ...')"""
        cls._logger().info(msg, *args)

    @classmethod
    def _warn(cls, msg: str, *args: Any) -> None:
        """Warning log।"""
        cls._logger().warning(msg, *args)

    @classmethod
    def _err_log(cls, msg: str, *args: Any) -> None:
        """Error log — replaces: logger.error('ClassName.method: ...')"""
        cls._logger().error(msg, *args)

    # ── ServiceResult shorthand ────────────────────────────────────────────────

    @classmethod
    def _ok(cls, **kwargs: Any) -> Dict[str, Any]:
        """Return a success result। Delegates to ServiceResult.ok()।"""
        return ServiceResult.ok(**kwargs)

    @classmethod
    def _err(cls, error: str, code: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """Return an error result। Delegates to ServiceResult.err()।"""
        return ServiceResult.err(error, code=code, **kwargs)

    @classmethod
    def _err_exc(cls, exc: Exception, code: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert an exception to an error result AND log it।
        Most common except-block pattern in one call।

        Usage:
            except Exception as e:
                return cls._err_exc(e)

            except ValueError as e:
                return cls._err_exc(e, code='VALIDATION_ERROR')
        """
        cls._err_log('%s error: %s', cls.__name__, exc)
        return ServiceResult.from_exception(exc, code=code)

    @classmethod
    def _skipped(cls, reason: str) -> Dict[str, Any]:
        """Return a skipped result (no-op, already processed, etc.)।"""
        return ServiceResult.skipped(reason)

    @classmethod
    def _paginated(cls, items: list, total: int, page: int, page_size: int) -> Dict[str, Any]:
        """Return a paginated list result।"""
        return ServiceResult.paginated(items, total, page, page_size)

    # ── Common model helpers ───────────────────────────────────────────────────

    @classmethod
    def _get_loyalty_points(cls, customer, select_for_update: bool = False):
        """
        DRY: Get LoyaltyPoints for a customer with consistent error handling।
        Replaces repeated:
            lp = LoyaltyPoints.objects.filter(customer=customer).first()
            if not lp: return {'success': False, 'error': 'Points wallet not found'}
        """
        from ..models.points import LoyaltyPoints
        qs = LoyaltyPoints.objects
        if select_for_update:
            qs = qs.select_for_update()
        try:
            return qs.get(customer=customer)
        except LoyaltyPoints.DoesNotExist:
            return None

    @classmethod
    def _resolve_tenant(cls, customer=None, request=None, tenant=None):
        """
        DRY: Resolve tenant from available sources (in priority order)।
        Replaces repeated: getattr(customer, 'tenant', None)
        """
        if tenant:
            return tenant
        if request:
            t = getattr(request, 'tenant', None)
            if t:
                return t
        if customer:
            return getattr(customer, 'tenant', None)
        return None
