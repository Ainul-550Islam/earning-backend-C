"""
TemplateViewSet
Exposes SmartLinkTemplate CRUD + apply-template action.
Service: SmartLinkTemplateService
Model:   SmartLinkTemplate (models/extensions/smartlink_schedule.py)
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from api.smartlink.models.extensions.smartlink_schedule import SmartLinkTemplate
from api.smartlink.serializers.SmartLinkTemplateSerializer import (
    SmartLinkTemplateSerializer,
    SmartLinkTemplateListSerializer,
    ApplyTemplateSerializer,
)
from ..services.template.SmartLinkTemplateService import SmartLinkTemplateService
from api.smartlink.permissions import IsSmartLinkOwnerOrAdmin

import logging
logger = logging.getLogger('smartlink.viewsets.template')


class TemplateViewSet(viewsets.ModelViewSet):
    """
    Manage SmartLink configuration templates.

    list   GET    /api/smartlink/templates/
    create POST   /api/smartlink/templates/
    detail GET    /api/smartlink/templates/{id}/
    update PATCH  /api/smartlink/templates/{id}/
    delete DELETE /api/smartlink/templates/{id}/

    Actions:
      POST GET /api/smartlink/templates/public/
      POST     /api/smartlink/templates/{id}/apply/
      POST     /api/smartlink/templates/from-smartlink/{sl_pk}/
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['use_count', 'created_at', 'name']
    ordering = ['-use_count']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._template_svc = SmartLinkTemplateService()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SmartLinkTemplate.objects.all().select_related('publisher')
        # Publishers see their own templates + all public ones
        from django.db.models import Q
        return SmartLinkTemplate.objects.filter(
            Q(publisher=user) | Q(is_public=True)
        ).select_related('publisher')

    def get_serializer_class(self):
        if self.action == 'list':
            return SmartLinkTemplateListSerializer
        return SmartLinkTemplateSerializer

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)
        logger.info(
            f"Template '{serializer.instance.name}' created by "
            f"{self.request.user.username}"
        )

    def update(self, request, *args, **kwargs):
        template = self.get_object()
        # Publishers can only edit their own templates
        if not request.user.is_staff and template.publisher != request.user:
            return Response(
                {'detail': 'You can only edit your own templates.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        template = self.get_object()
        if not request.user.is_staff and template.publisher != request.user:
            return Response(
                {'detail': 'You can only delete your own templates.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    # ── Extra actions ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='public')
    def public(self, request):
        """
        GET /api/smartlink/templates/public/
        List all public templates available to every publisher.
        Optionally filter by category: ?category=gaming
        """
        category = request.query_params.get('category')
        templates = self._template_svc.get_public_templates(category=category)
        return Response(templates)

    @action(detail=True, methods=['post'], url_path='apply')
    def apply(self, request, pk=None):
        """
        POST /api/smartlink/templates/{id}/apply/
        Create a new SmartLink from this template.
        Body: {"override": {"name": "My Link", ...}}
        """
        template = self.get_object()
        serializer = ApplyTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            sl = self._template_svc.create_smartlink_from_template(
                template=template,
                publisher=request.user,
                override=serializer.validated_data.get('override') or {},
            )
        except Exception as e:
            logger.error(
                f"Template apply failed: template={template.pk} "
                f"user={request.user.username} error={e}"
            )
            return Response(
                {'detail': f'Failed to create SmartLink from template: {e}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from api.smartlink.serializers.SmartLinkSerializer import SmartLinkSerializer
        return Response(
            {
                'message': f"SmartLink [{sl.slug}] created from template '{template.name}'.",
                'smartlink': SmartLinkSerializer(sl).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path=r'from-smartlink/(?P<sl_pk>[^/.]+)')
    def from_smartlink(self, request, sl_pk=None):
        """
        POST /api/smartlink/templates/from-smartlink/{sl_pk}/
        Save an existing SmartLink's config as a new template.
        Body: {"name": "My Template", "is_public": false}
        """
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        qs = SmartLink.objects.all() if request.user.is_staff else SmartLink.objects.filter(
            publisher=request.user
        )
        sl = get_object_or_404(qs, pk=sl_pk)

        name = request.data.get('name', f'Template from {sl.name}')
        is_public = bool(request.data.get('is_public', False))

        try:
            template = self._template_svc.create_template_from_smartlink(
                smartlink=sl,
                publisher=request.user,
                name=name,
                is_public=is_public,
            )
        except Exception as e:
            return Response(
                {'detail': f'Failed to save template: {e}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SmartLinkTemplateSerializer(template).data,
            status=status.HTTP_201_CREATED,
        )
