# api/djoyalty/viewsets/advanced/CustomerProfileViewSet.py
"""
CustomerProfileViewSet -- full customer profile + stats API.

Exposes CustomerProfileService which was built but had ZERO API endpoints.

Endpoints:
  GET  /profile/me/             -- own full profile + stats
  GET  /profile/{id}/           -- admin: any customer profile
  POST /profile/search/         -- admin: search customers
  POST /profile/{id}/deactivate/ -- admin: soft-deactivate
  POST /profile/{id}/reactivate/ -- admin: reactivate
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from ...models.core import Customer
from ...serializers.CustomerSerializer import CustomerSerializer
from ...services.CustomerProfileService import CustomerProfileService
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...throttles import DjoyaltyUserThrottle
from ...mixins import DjoyaltyBaseViewSet


class CustomerProfileViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    Customer profile endpoints.
    Regular users: only own profile.
    Admins: any customer.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CustomerSerializer
    pagination_class = DjoyaltyPagePagination
    throttle_classes = [DjoyaltyUserThrottle]

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return Customer.objects.all().select_related('tenant')
        return Customer.objects.filter(
            user=self.request.user
        ).select_related('tenant')

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """
        Authenticated user's own full loyalty profile + stats.
        """
        customer = Customer.objects.filter(user=request.user).first()
        if not customer:
            return Response(
                {'error': 'No loyalty account found for this user.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        stats = CustomerProfileService.get_full_stats(customer)
        return Response(stats)

    def retrieve(self, request, *args, **kwargs):
        """
        GET /profile/{id}/ -- admin only for other customers.
        Own profile is allowed.
        """
        customer = get_object_or_404(Customer, pk=kwargs['pk'])
        is_admin = request.user.is_staff or request.user.is_superuser
        is_own = getattr(customer, 'user', None) == request.user
        if not is_admin and not is_own:
            return Response(
                {'error': 'Permission denied.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        stats = CustomerProfileService.get_full_stats(customer)
        return Response(stats)

    @action(
        detail=False,
        methods=['post'],
        url_path='search',
        permission_classes=[IsLoyaltyAdmin],
    )
    def search(self, request):
        """
        Admin: search customers by code / name / email / phone.
        """
        query = request.data.get('q', '').strip()
        if len(query) < 2:
            return Response(
                {'error': 'Search query must be at least 2 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit = min(int(request.data.get('limit', 20)), 100)
        tenant = getattr(request, 'tenant', None)
        customers = CustomerProfileService.search(query, tenant=tenant, limit=limit)
        serializer = CustomerSerializer(customers, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data,
        })

    @action(
        detail=True,
        methods=['post'],
        url_path='deactivate',
        permission_classes=[IsLoyaltyAdmin],
    )
    def deactivate(self, request, pk=None):
        """Admin: soft-deactivate a customer account."""
        customer = get_object_or_404(Customer, pk=pk)
        reason = request.data.get('reason', f'Deactivated by {request.user}')
        CustomerProfileService.deactivate(customer, reason=reason)
        return Response({'status': 'deactivated', 'customer': customer.code})

    @action(
        detail=True,
        methods=['post'],
        url_path='reactivate',
        permission_classes=[IsLoyaltyAdmin],
    )
    def reactivate(self, request, pk=None):
        """Admin: reactivate a customer account."""
        customer = get_object_or_404(Customer, pk=pk)
        CustomerProfileService.reactivate(customer)
        return Response({'status': 'reactivated', 'customer': customer.code})
