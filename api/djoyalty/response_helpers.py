# api/djoyalty/response_helpers.py
"""
DjoyaltyResponse — Single canonical class for all HTTP response construction।

DRY FIX: Previously 200+ viewset methods returned inline Response() calls:
    return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'error': str(e)}, status=500)
    return Response({'error': 'customer_id required'}, status=400)
    return Response({'error': 'Customer not found'}, status=404)
    return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

The same message had different status codes (400 vs HTTP_400_BAD_REQUEST),
different error key capitalisation, trailing dots/no dots — inconsistent API。

All viewsets MUST use DjoyaltyResponse instead of inline Response() calls।

Usage:
    return DjoyaltyResponse.ok({'balance': 500})
    return DjoyaltyResponse.err('Customer not found.', 404)
    return DjoyaltyResponse.customer_not_found()
    return DjoyaltyResponse.customer_required()
    return DjoyaltyResponse.from_service(service_result)
"""
from rest_framework import status
from rest_framework.response import Response
from typing import Any, Dict, Optional


class DjoyaltyResponse:
    """
    Factory for canonical HTTP responses।
    Never instantiated — use class-methods only।
    """

    # ── Success responses ──────────────────────────────────────────────────────

    @classmethod
    def ok(cls, data: Any = None, http_status: int = status.HTTP_200_OK) -> Response:
        """Standard 200 OK।"""
        return Response(data or {}, status=http_status)

    @classmethod
    def created(cls, data: Any = None) -> Response:
        """201 Created — for POST that creates a resource।"""
        return Response(data or {}, status=status.HTTP_201_CREATED)

    @classmethod
    def no_content(cls) -> Response:
        """204 No Content — for DELETE actions।"""
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Error responses ────────────────────────────────────────────────────────

    @classmethod
    def err(cls, message: str, http_status: int = status.HTTP_400_BAD_REQUEST,
            code: Optional[str] = None) -> Response:
        """
        Generic error response।
        Replaces: return Response({'error': msg}, status=400)
        """
        payload: Dict[str, Any] = {'error': message}
        if code:
            payload['code'] = code
        return Response(payload, status=http_status)

    @classmethod
    def bad_request(cls, message: str, code: Optional[str] = None) -> Response:
        """400 Bad Request।"""
        return cls.err(message, status.HTTP_400_BAD_REQUEST, code=code)

    @classmethod
    def forbidden(cls, message: str = 'Access denied.') -> Response:
        """403 Forbidden।"""
        return cls.err(message, status.HTTP_403_FORBIDDEN)

    @classmethod
    def not_found(cls, message: str = 'Not found.') -> Response:
        """404 Not Found।"""
        return cls.err(message, status.HTTP_404_NOT_FOUND)

    @classmethod
    def server_error(cls, message: str = 'An internal error occurred.') -> Response:
        """500 Internal Server Error।"""
        return cls.err(message, status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── Named shorthand responses (eliminates most repeated messages) ──────────

    @classmethod
    def customer_not_found(cls) -> Response:
        """
        Replaces 33 instances of:
            Response({'error': 'Customer not found'}, status=404)
            Response({'error': 'Customer not found.'}, status=HTTP_404_NOT_FOUND)
        """
        return cls.not_found('Customer not found.')

    @classmethod
    def customer_required(cls) -> Response:
        """
        Replaces 22 instances of:
            Response({'error': 'customer_id required'}, status=400)
            Response({'error': 'customer_id required'}, status=HTTP_400_BAD_REQUEST)
        """
        return cls.bad_request('customer_id is required.')

    @classmethod
    def reference_required(cls) -> Response:
        """
        Replaces 8 instances of:
            Response({'error': 'reference_id is required ...'}, status=400)
        """
        return cls.bad_request('reference_id is required.')

    @classmethod
    def token_required(cls) -> Response:
        """Replaces: Response({'error': 'token required'}, status=400)"""
        return cls.bad_request('token is required.')

    # ── Service result bridge ──────────────────────────────────────────────────

    @classmethod
    def from_service(cls, result: Dict[str, Any],
                     ok_status: int = status.HTTP_200_OK,
                     err_status: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """
        Convert a ServiceResult dict directly to an HTTP Response।

        Replaces the pattern:
            if not result['success']:
                return Response({'error': result['error']}, status=400)
            return Response(result, status=200)

        Usage:
            result = CashoutService.create_request(...)
            return DjoyaltyResponse.from_service(result)
            # or for creation:
            return DjoyaltyResponse.from_service(result, ok_status=201)
        """
        if result.get('success', False):
            return Response(result, status=ok_status)
        error = result.get('error', 'Service error.')
        code  = result.get('code')
        payload: Dict[str, Any] = {'error': error}
        if code:
            payload['code'] = code
        return Response(payload, status=err_status)

    @classmethod
    def from_service_created(cls, result: Dict[str, Any]) -> Response:
        """from_service() shorthand for 201 Created on success।"""
        return cls.from_service(result, ok_status=status.HTTP_201_CREATED)
