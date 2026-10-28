# api/djoyalty/service_result.py
"""
ServiceResult — Single canonical structure for all service return values।

DRY FIX: Previously 97 places in services returned
    {'success': False, 'error': 'some message'}
and 29 places returned
    {'success': True, 'key': 'value', ...}
as raw inline dicts — inconsistent keys, inconsistent structure,
no type-safety, and impossible to grep systematically।

All services MUST use ServiceResult instead of raw dicts।
Callers check results with:
    result = SomeService.do_thing(...)
    if not ServiceResult.is_ok(result):
        return DjoyaltyResponse.from_service(result)

ServiceResult guarantees:
    ok  → {'success': True,  **kwargs}
    err → {'success': False, 'error': str, **kwargs}
"""
from __future__ import annotations
from typing import Any, Dict, Optional


class ServiceResult:
    """
    Factory for canonical service return dicts।
    Never instantiated — use class-methods only।

    Example:
        return ServiceResult.ok(customer=customer, points=100)
        return ServiceResult.err('Insufficient balance.')
        return ServiceResult.err('Invalid tier.', code='INVALID_TIER')
    """

    @classmethod
    def ok(cls, **kwargs: Any) -> Dict[str, Any]:
        """
        Successful service result।
        Always sets success=True as first key for clarity in logs/debug।

        Usage:
            return ServiceResult.ok(cashout=obj, reference='CO-001')
            return ServiceResult.ok(points_added=100, balance_after=500)
        """
        return {'success': True, **kwargs}

    @classmethod
    def err(cls, error: str, code: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """
        Failed service result।
        Always sets success=False।
        Optional `code` for machine-readable error classification।

        Usage:
            return ServiceResult.err('Insufficient points balance.')
            return ServiceResult.err('Rate not found.', code='NO_RATE')
            return ServiceResult.err('Duplicate cashout.', code='DUPLICATE', pending_id=42)
        """
        result: Dict[str, Any] = {'success': False, 'error': error, **kwargs}
        if code:
            result['code'] = code
        return result

    @classmethod
    def is_ok(cls, result: Dict[str, Any]) -> bool:
        """Check if a service result indicates success।"""
        return bool(result.get('success', False))

    @classmethod
    def is_err(cls, result: Dict[str, Any]) -> bool:
        """Check if a service result indicates failure।"""
        return not cls.is_ok(result)

    @classmethod
    def error_message(cls, result: Dict[str, Any]) -> str:
        """Extract error message from a failed result।"""
        return result.get('error', 'Unknown error')

    @classmethod
    def error_code(cls, result: Dict[str, Any]) -> Optional[str]:
        """Extract error code from a failed result (may be None)।"""
        return result.get('code')

    @classmethod
    def from_exception(cls, exc: Exception, code: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert an exception into a ServiceResult error।
        Use in except blocks to avoid repeating str(e) everywhere।

        Usage:
            except ValueError as e:
                return ServiceResult.from_exception(e, code='VALIDATION_ERROR')
        """
        return cls.err(str(exc), code=code)

    @classmethod
    def skipped(cls, reason: str) -> Dict[str, Any]:
        """
        Indicates the operation was skipped (not an error, not a success)।
        E.g., task already processed, idempotent replay, no-op।

        Usage:
            return ServiceResult.skipped('No reference_id provided.')
        """
        return {'success': True, 'skipped': True, 'reason': reason}

    @classmethod
    def paginated(cls, items: list, total: int, page: int, page_size: int) -> Dict[str, Any]:
        """
        Paginated list result। Eliminates repeated pagination dict construction।
        """
        return {
            'success': True,
            'results': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 0,
            'has_next': page * page_size < total,
            'has_prev': page > 1,
        }
