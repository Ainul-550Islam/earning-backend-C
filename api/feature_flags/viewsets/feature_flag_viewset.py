"""
Feature Flag viewset for Feature Flags & A/B Testing.

FIX: added authentication/permissions (was completely open before),
pagination/filtering, and current-user attribution for the audit trail.

NEW: exposes several previously-floating or entirely-missing
capabilities as real endpoints — clone, restore, bulk activate/pause,
change-request approval workflow, and version rollback.
"""
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response

from ..models.feature_flag import FeatureFlag
from ..models.approval import FlagChangeRequest
from ..models.versioning import FeatureFlagVersion
from ..models.scheduling import ScheduledChange
from ..serializers.feature_flag_serializer import FeatureFlagSerializer, FeatureFlagListSerializer
from ..flag_engine import FlagEngine
from ..permissions import IsAuthenticated, CanViewFlags, CanEditFlags, CanApproveChanges
from ..utils import ContextExtractor
from ..signals import set_current_user


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """
    Viewset for FeatureFlag model.
    """

    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer

    # NEW: was missing entirely. CanViewFlags allows safe methods to
    # anyone with view access; CanEditFlags additionally gates writes.
    permission_classes = [IsAuthenticated, CanViewFlags, CanEditFlags]

    # NEW: pagination is on by default via REST_FRAMEWORK settings;
    # filtering/search/ordering were entirely absent before.
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'environment', 'flag_type', 'organization']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name', 'rollout_percentage']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return FeatureFlagListSerializer
        return FeatureFlagSerializer

    def get_queryset(self):
        """
        NEW: optional organization-scoping. If the requesting user belongs
        to organizations, restrict results to flags with no organization
        (global) or one of theirs. Single-tenant deployments (no
        Organization rows in use) are completely unaffected.
        """
        queryset = super().get_queryset()
        user = self.request.user
        org_ids = list(user.organizations.values_list('id', flat=True)) if user.is_authenticated else []
        if org_ids:
            from django.db.models import Q
            queryset = queryset.filter(Q(organization__isnull=True) | Q(organization_id__in=org_ids))
        return queryset

    def perform_create(self, serializer):
        """NEW: stash the requesting user so the post_save signal can attribute the AuditLog entry."""
        set_current_user(self.request.user)
        serializer.save()

    def perform_update(self, serializer):
        set_current_user(self.request.user)
        serializer.save()

    def perform_destroy(self, instance):
        set_current_user(self.request.user)
        instance.delete()

    # ------------------------------------------------------------------
    # Existing actions (kept, with the now-fixed environment-aware cache
    # invalidation and ContextExtractor for `check`).
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a flag."""
        flag = self.get_object()
        flag.status = FeatureFlag.Status.ACTIVE
        set_current_user(request.user)
        flag.save()

        return Response({'success': True, 'message': f'Flag {flag.name} activated successfully'})

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a flag."""
        flag = self.get_object()
        flag.status = FeatureFlag.Status.PAUSED
        set_current_user(request.user)
        flag.save()

        return Response({'success': True, 'message': f'Flag {flag.name} paused successfully'})

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a flag."""
        flag = self.get_object()
        flag.status = FeatureFlag.Status.ARCHIVED
        set_current_user(request.user)
        flag.save()

        return Response({'success': True, 'message': f'Flag {flag.name} archived successfully'})

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active flags."""
        flags = self.filter_queryset(self.get_queryset()).filter(status=FeatureFlag.Status.ACTIVE)
        page = self.paginate_queryset(flags)
        serializer = self.get_serializer(page if page is not None else flags, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def check(self, request, pk=None):
        """Check if a flag is enabled for a given user/context."""
        flag = self.get_object()
        engine = FlagEngine()

        context = ContextExtractor.from_query_params(request.query_params)

        is_enabled = engine.is_enabled(flag.name, context, flag.environment)
        value = engine.get_value(flag.name, context, environment=flag.environment)

        return Response({'enabled': is_enabled, 'value': value})

    # ------------------------------------------------------------------
    # NEW actions — floating-code exposure & missing-component fixes
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """NEW: restore an archived flag back to draft status."""
        flag = self.get_object()
        flag.status = FeatureFlag.Status.DRAFT
        set_current_user(request.user)
        flag.save()

        return Response({'success': True, 'message': f'Flag {flag.name} restored to draft'})

    @action(detail=False, methods=['post'], url_path='clone')
    def clone_flag(self, request):
        """NEW: clone an existing flag (and its variants) under a new name."""
        source_name = request.data.get('source_name')
        new_name = request.data.get('new_name')
        environment = request.data.get('environment')

        if not source_name or not new_name:
            return Response({'error': 'source_name and new_name are required'}, status=400)

        try:
            source = FeatureFlag.objects.get(name=source_name, environment=environment or 'production')
        except FeatureFlag.DoesNotExist:
            return Response({'error': f"Source flag '{source_name}' not found"}, status=404)

        if FeatureFlag.objects.filter(name=new_name, environment=source.environment).exists():
            return Response({'error': f"A flag named '{new_name}' already exists in this environment"}, status=400)

        set_current_user(request.user)
        new_flag = FeatureFlag.objects.create(
            name=new_name,
            description=f"Clone of {source_name}",
            flag_type=source.flag_type,
            status=FeatureFlag.Status.DRAFT,
            default_value=source.default_value,
            rollout_percentage=0,
            targeting_rules=source.targeting_rules,
            metadata=source.metadata,
            tags=source.tags,
            owner=source.owner,
            team=source.team,
            environment=source.environment,
            organization=source.organization,
        )

        from ..models.flag_variant import FlagVariant
        for variant in FlagVariant.objects.filter(flag=source):
            FlagVariant.objects.create(
                flag=new_flag,
                name=variant.name,
                description=variant.description,
                value=variant.value,
                weight=variant.weight,
                is_control=variant.is_control,
                is_active=variant.is_active,
                metadata=variant.metadata,
            )

        serializer = self.get_serializer(new_flag)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """NEW: bulk enable/disable/pause a list of flags by name (previously
        documented in the audit as missing entirely)."""
        names = request.data.get('names', [])
        new_status = request.data.get('status')

        if not names or new_status not in FeatureFlag.Status.values:
            return Response({'error': 'names (list) and a valid status are required'}, status=400)

        set_current_user(request.user)
        updated = 0
        for flag in FeatureFlag.objects.filter(name__in=names):
            flag.status = new_status
            flag.save()
            updated += 1

        return Response({'success': True, 'updated_count': updated})

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """NEW: list version history for a flag (Missing Component: Versioning)."""
        flag = self.get_object()
        versions = FeatureFlagVersion.objects.filter(flag=flag)
        return Response([
            {
                'version_number': v.version_number,
                'config': v.config,
                'created_by': getattr(v.created_by, 'username', None),
                'created_at': v.created_at,
            }
            for v in versions
        ])

    @action(detail=True, methods=['post'])
    def rollback(self, request, pk=None):
        """NEW: rollback a flag to a previous version (Missing Component: Versioning)."""
        flag = self.get_object()
        version_number = request.data.get('version_number')

        try:
            version = FeatureFlagVersion.objects.get(flag=flag, version_number=version_number)
        except FeatureFlagVersion.DoesNotExist:
            return Response({'error': f'Version {version_number} not found for this flag'}, status=404)

        protected_fields = {'id', 'created_at', 'updated_at', 'name', 'environment'}
        for key, value in version.config.items():
            if key not in protected_fields and hasattr(flag, key):
                setattr(flag, key, value)

        set_current_user(request.user)
        flag.save()

        return Response({'success': True, 'message': f'Flag rolled back to version {version_number}'})

    @action(detail=True, methods=['post'])
    def request_change(self, request, pk=None):
        """NEW: submit a proposed change for review instead of applying it
        directly (Missing Component: Approval Workflows)."""
        flag = self.get_object()
        change_request = FlagChangeRequest.objects.create(
            flag=flag,
            requested_by=request.user,
            requested_changes=request.data,
        )
        return Response({
            'id': change_request.id,
            'status': change_request.status,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveChanges])
    def approve_change(self, request, pk=None):
        """NEW: approve and apply a pending change request."""
        flag = self.get_object()
        change_id = request.data.get('change_request_id')

        try:
            change = FlagChangeRequest.objects.get(id=change_id, flag=flag, status=FlagChangeRequest.Status.PENDING)
        except FlagChangeRequest.DoesNotExist:
            return Response({'error': 'Pending change request not found'}, status=404)

        for key, value in change.requested_changes.items():
            if hasattr(flag, key) and key not in ('id', 'created_at', 'updated_at'):
                setattr(flag, key, value)

        set_current_user(request.user)
        flag.save()

        change.status = FlagChangeRequest.Status.DEPLOYED
        change.reviewed_by = request.user
        change.reviewed_at = timezone.now()
        change.deployed_at = timezone.now()
        change.save()

        return Response({'success': True, 'status': change.status})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveChanges])
    def reject_change(self, request, pk=None):
        """NEW: reject a pending change request."""
        flag = self.get_object()
        change_id = request.data.get('change_request_id')

        try:
            change = FlagChangeRequest.objects.get(id=change_id, flag=flag, status=FlagChangeRequest.Status.PENDING)
        except FlagChangeRequest.DoesNotExist:
            return Response({'error': 'Pending change request not found'}, status=404)

        change.status = FlagChangeRequest.Status.REJECTED
        change.reviewed_by = request.user
        change.review_comment = request.data.get('comment', '')
        change.reviewed_at = timezone.now()
        change.save()

        return Response({'success': True, 'status': change.status})

    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """NEW: schedule a future activate/pause/archive (Missing Component: Scheduling)."""
        flag = self.get_object()
        change_type = request.data.get('change_type')
        scheduled_for = request.data.get('scheduled_for')

        if change_type not in ScheduledChange.ChangeType.values or not scheduled_for:
            return Response({'error': 'change_type and scheduled_for are required'}, status=400)

        scheduled = ScheduledChange.objects.create(
            flag=flag,
            change_type=change_type,
            scheduled_for=scheduled_for,
            target_rollout_percentage=request.data.get('target_rollout_percentage'),
            created_by=request.user,
        )

        return Response({'success': True, 'id': scheduled.id}, status=status.HTTP_201_CREATED)
