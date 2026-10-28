# api/admin_panel/viewsets/AdminSessionViewSet.py
"""AdminSessionViewSet — active sessions management + force logout."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..models.activity import AdminSession
from ..pagination import AdminPagination
from ..filters import AdminSessionFilter


class AdminSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """View and manage active admin sessions. Supports force-logout."""
    permission_classes = [IsAdminUser]
    pagination_class = AdminPagination
    filterset_class = AdminSessionFilter

    def get_serializer_class(self):
        from ..serializers.AdminSessionSerializer import AdminSessionSerializer
        return AdminSessionSerializer

    def get_queryset(self):
        qs = AdminSession.objects.select_related('user', 'force_logout_by').order_by('-started_at')
        # Non-superadmins can only see their own sessions
        if not self.request.user.is_superuser:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=['get'])
    def active(self, request):
        """List only currently active sessions."""
        sessions = self.get_queryset().filter(is_active=True)
        page = self.paginate_queryset(sessions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(sessions, many=True)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=True, methods=['post'])
    def force_logout(self, request, pk=None):
        """Force-logout a specific admin session."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superadmins can force-logout sessions.'},
                status=status.HTTP_403_FORBIDDEN
            )
        session = self.get_object()
        if not session.is_active:
            return Response({'error': 'Session is already ended.'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', 'Force logged out by admin.')
        session.force_logout(by_user=request.user, reason=reason)

        return Response({
            'success': True,
            'message': f'Session for {session.user.username} has been force-logged out.',
        })

    @action(detail=False, methods=['post'])
    def force_logout_all(self, request):
        """Force-logout ALL active admin sessions (except the current one)."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superadmins can force-logout all sessions.'},
                status=status.HTTP_403_FORBIDDEN
            )
        from django.utils import timezone
        current_session_key = request.session.session_key
        sessions = AdminSession.objects.filter(is_active=True).exclude(
            session_key=current_session_key
        )
        count = sessions.count()
        for session in sessions:
            session.force_logout(
                by_user=request.user,
                reason='Force logout all by superadmin.'
            )
        return Response({
            'success': True,
            'message': f'{count} sessions force-logged out.',
            'count': count,
        })

    @action(detail=False, methods=['get'])
    def my_sessions(self, request):
        """Get current user's own session history."""
        sessions = AdminSession.objects.filter(
            user=request.user
        ).order_by('-started_at')[:20]
        serializer = self.get_serializer(sessions, many=True)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Session statistics."""
        from django.db.models import Count
        total = AdminSession.objects.count()
        active = AdminSession.objects.filter(is_active=True).count()
        by_status = AdminSession.objects.values('status').annotate(count=Count('id'))
        return Response({
            'total': total,
            'active': active,
            'by_status': list(by_status),
        })