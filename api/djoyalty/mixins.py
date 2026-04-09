# api/djoyalty/mixins.py
"""
ViewSet mixins for Djoyalty।
Tenant isolation, audit logging, standard responses।
"""
import logging
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('djoyalty.mixins')


class DjoyaltyTenantMixin:
    """
    Tenant isolation mixin।
    সব ViewSet এ যোগ করুন।
    get_queryset() এ tenant filter apply করে।
    """

    def get_tenant(self):
        """Request থেকে tenant নিরাপদে নাও।"""
        return getattr(self.request, 'tenant', None)

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = self.get_tenant()
        if tenant is not None:
            # tenant field আছে এমন model এর জন্য filter করো
            if hasattr(qs.model, 'tenant'):
                qs = qs.filter(tenant=tenant)
        return qs

    def perform_create(self, serializer):
        """Create এ tenant auto-inject।"""
        tenant = self.get_tenant()
        if tenant and 'tenant' not in serializer.validated_data:
            serializer.save(tenant=tenant)
        else:
            serializer.save()


class DjoyaltyAuditMixin:
    """
    Audit logging mixin।
    সব write operations log করে।
    """

    def perform_create(self, serializer):
        instance = serializer.save()
        logger.info(
            'Created %s id=%s by user=%s',
            instance.__class__.__name__,
            instance.pk,
            getattr(self.request.user, 'id', 'anonymous'),
        )
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        logger.info(
            'Updated %s id=%s by user=%s',
            instance.__class__.__name__,
            instance.pk,
            getattr(self.request.user, 'id', 'anonymous'),
        )
        return instance

    def perform_destroy(self, instance):
        logger.info(
            'Deleted %s id=%s by user=%s',
            instance.__class__.__name__,
            instance.pk,
            getattr(self.request.user, 'id', 'anonymous'),
        )
        instance.delete()


class DjoyaltyStandardResponseMixin:
    """
    Standard response format mixin।
    Consistent success/error responses।
    """

    def success_response(self, data=None, message='Success', status_code=status.HTTP_200_OK):
        return Response({
            'success': True,
            'message': message,
            'data': data,
        }, status=status_code)

    def created_response(self, data=None, message='Created successfully'):
        return self.success_response(data, message, status.HTTP_201_CREATED)

    def error_response(self, error='error', message='An error occurred', status_code=status.HTTP_400_BAD_REQUEST, extra=None):
        body = {'success': False, 'error': error, 'message': message}
        if extra:
            body.update(extra)
        return Response(body, status=status_code)


class DjoyaltyListMixin:
    """
    Enhanced list mixin with stats।
    """

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return response
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'results': serializer.data})


class DjoyaltyFullMixin(DjoyaltyTenantMixin, DjoyaltyAuditMixin, DjoyaltyStandardResponseMixin):
    """
    All mixins combined — most ViewSets এ এটি ব্যবহার করুন।
    Usage:
        class CustomerViewSet(DjoyaltyFullMixin, viewsets.ModelViewSet):
            ...
    """
    pass
