from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models.publisher import PublisherDomain
from ..serializers.DomainSerializer import DomainSerializer
from ..services.core.DomainService import DomainService
from ..permissions import IsPublisher


class DomainViewSet(viewsets.ModelViewSet):
    """Manage custom domains for publishers."""
    serializer_class = DomainSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.domain_service = DomainService()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return PublisherDomain.objects.all()
        return PublisherDomain.objects.filter(publisher=user)

    def perform_create(self, serializer):
        domain = serializer.validated_data['domain']
        domain_obj = self.domain_service.initiate_verification(self.request.user, domain)
        serializer.instance = domain_obj

    @action(detail=True, methods=['post'], url_path='verify')
    def verify(self, request, pk=None):
        """POST /domains/{id}/verify/ — check DNS TXT record."""
        domain_obj = self.get_object()
        try:
            verified = self.domain_service.verify(domain_obj)
            return Response({'verified': verified, 'domain': domain_obj.domain})
        except Exception as e:
            return Response({'verified': False, 'error': str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @action(detail=True, methods=['post'], url_path='check-ssl')
    def check_ssl(self, request, pk=None):
        """POST /domains/{id}/check-ssl/ — check SSL certificate."""
        domain_obj = self.get_object()
        result = self.domain_service.check_ssl(domain_obj)
        return Response(result)

    @action(detail=True, methods=['post'], url_path='set-primary')
    def set_primary(self, request, pk=None):
        """POST /domains/{id}/set-primary/ — set as primary domain."""
        domain_obj = self.get_object()
        PublisherDomain.objects.filter(publisher=request.user).update(is_primary=False)
        domain_obj.is_primary = True
        domain_obj.save(update_fields=['is_primary', 'updated_at'])
        return Response({'status': 'set_as_primary', 'domain': domain_obj.domain})
