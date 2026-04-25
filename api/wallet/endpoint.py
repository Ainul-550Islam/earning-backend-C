# api/wallet/endpoint.py
"""
Endpoint helpers — reusable view building blocks.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger("wallet.endpoint")


def wallet_endpoint(methods=["GET"], auth=True, admin=False):
    """
    Decorator factory for simple wallet API endpoints.
    Usage:
        @wallet_endpoint(methods=["POST"], auth=True)
        def my_view(request):
            return {"result": "ok"}
    """
    perms = [IsAdminUser()] if admin else ([IsAuthenticated()] if auth else [])

    def decorator(func):
        @api_view(methods)
        @permission_classes([type(p) for p in perms] if perms else [])
        def wrapper(request, *args, **kwargs):
            try:
                result = func(request, *args, **kwargs)
                if isinstance(result, Response):
                    return result
                return Response({"success": True, "data": result})
            except Exception as e:
                logger.error(f"Endpoint error {func.__name__}: {e}", exc_info=True)
                return Response({"success": False, "error": str(e)},
                                status=status.HTTP_400_BAD_REQUEST)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


def paginated_list_endpoint(queryset_func, serializer_class, filterset_class=None):
    """
    Build a simple paginated list endpoint from a queryset function.
    Usage:
        urlpatterns += [
            path("recent/", paginated_list_endpoint(
                lambda req: WalletTransaction.objects.filter(wallet__user=req.user),
                WalletTransactionSerializer,
            )),
        ]
    """
    from rest_framework.generics import ListAPIView

    class AutoListView(ListAPIView):
        serializer_class   = serializer_class
        filterset_class    = filterset_class
        permission_classes = [IsAuthenticated]

        def get_queryset(self):
            return queryset_func(self.request)

    return AutoListView.as_view()
