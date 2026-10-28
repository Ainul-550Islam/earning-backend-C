# cms/viewsets_new/missing_viewsets_group1.py
"""
Missing ViewSets — Group 1

Covers models with NO existing API endpoint:
  - ABTest, ABTestVariant, ABTestParticipant, ABTestResult
  - ContentComment, CommentReaction
  - Announcement, Notification, NotificationTemplate, EmailTemplate,
    Testimonial, SocialLink, PopupDismissal, UserContentInteraction
  - LandingPage
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging

logger = logging.getLogger('cms.viewsets.group1')


# ─────────────────────────────────────────────────────────────────────────────
# AB TESTING VIEWSETS
# ─────────────────────────────────────────────────────────────────────────────

class CommentReactionViewSet(viewsets.ModelViewSet):
    """
    CRUD for comment reactions (like/dislike/emoji).

    Endpoints:
        GET    /api/v3/comment-reactions/
        POST   /api/v3/comment-reactions/
        GET    /api/v3/comment-reactions/{id}/
        DELETE /api/v3/comment-reactions/{id}/
    """
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['comment', 'user', 'reaction_type']

    def get_queryset(self):
        from api.cms.models_new.comments import CommentReaction
        return CommentReaction.objects.select_related('comment', 'user')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import CommentReactionSerializer
        return CommentReactionSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─────────────────────────────────────────────────────────────────────────────
# EXTRAS VIEWSETS
# ─────────────────────────────────────────────────────────────────────────────

class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    CRUD for site-wide announcements.

    Endpoints:
        GET    /api/v3/announcements/
        POST   /api/v3/announcements/
        GET    /api/v3/announcements/{id}/
        PATCH  /api/v3/announcements/{id}/
        DELETE /api/v3/announcements/{id}/
        GET    /api/v3/announcements/active/
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'announcement_type', 'target_audience']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'priority', 'start_date']
    ordering = ['-priority', '-created_at']

    def get_queryset(self):
        from api.cms.models_new.extras import Announcement
        return Announcement.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import AnnouncementSerializer
        return AnnouncementSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return currently active announcements."""
        from api.cms.models_new.extras import Announcement
        now = timezone.now()
        qs = Announcement.objects.filter(
            is_active=True,
            start_date__lte=now
        ).filter(
            models_q_end=True
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class TestimonialViewSet(viewsets.ModelViewSet):
    """
    CRUD for testimonials.

    Endpoints:
        GET    /api/v3/testimonials/
        POST   /api/v3/testimonials/
        GET    /api/v3/testimonials/{id}/
        PATCH  /api/v3/testimonials/{id}/
        DELETE /api/v3/testimonials/{id}/
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_featured', 'is_approved', 'rating']
    search_fields = ['author_name', 'content', 'company']
    ordering_fields = ['created_at', 'rating', 'display_order']
    ordering = ['-is_featured', 'display_order']

    def get_queryset(self):
        from api.cms.models_new.extras import Testimonial
        qs = Testimonial.objects.all()
        if not self.request.user.is_staff:
            qs = qs.filter(is_approved=True)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import TestimonialSerializer
        return TestimonialSerializer


class SocialLinkViewSet(viewsets.ModelViewSet):
    """
    CRUD for social media links.

    Endpoints:
        GET    /api/v3/social-links/
        POST   /api/v3/social-links/
        GET    /api/v3/social-links/{id}/
        PATCH  /api/v3/social-links/{id}/
        DELETE /api/v3/social-links/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['platform', 'is_active']
    ordering = ['display_order']

    def get_queryset(self):
        from api.cms.models_new.extras import SocialLink
        return SocialLink.objects.filter(is_active=True)

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import SocialLinkSerializer
        return SocialLinkSerializer


class UserContentInteractionViewSet(viewsets.ModelViewSet):
    """
    CRUD for user-content interactions (views, likes, bookmarks).

    Endpoints:
        GET    /api/v3/content-interactions/
        POST   /api/v3/content-interactions/
        GET    /api/v3/content-interactions/{id}/
        DELETE /api/v3/content-interactions/{id}/
        GET    /api/v3/content-interactions/my/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['interaction_type', 'content_type', 'user']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.extras import UserContentInteraction
        qs = UserContentInteraction.objects.select_related('user')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import UserContentInteractionSerializer
        return UserContentInteractionSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my(self, request):
        """Return current user's interactions."""
        from api.cms.models_new.extras import UserContentInteraction
        qs = UserContentInteraction.objects.filter(user=request.user).order_by('-created_at')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGES VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class LandingPageViewSet(viewsets.ModelViewSet):
    """
    CRUD + publish/duplicate for landing pages.

    Endpoints:
        GET    /api/v3/landing-pages/
        POST   /api/v3/landing-pages/
        GET    /api/v3/landing-pages/{id}/
        PATCH  /api/v3/landing-pages/{id}/
        DELETE /api/v3/landing-pages/{id}/
        POST   /api/v3/landing-pages/{id}/publish/
        POST   /api/v3/landing-pages/{id}/duplicate/
        GET    /api/v3/landing-pages/{id}/analytics/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_published', 'template_type', 'created_by']
    search_fields = ['title', 'slug', 'meta_description']
    ordering_fields = ['created_at', 'published_at', 'title', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.landing_pages import LandingPage
        qs = LandingPage.objects.select_related('created_by')
        if not self.request.user.is_staff:
            qs = qs.filter(is_published=True)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import LandingPageSerializer
        return LandingPageSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish the landing page."""
        obj = self.get_object()
        obj.is_published = True
        obj.published_at = timezone.now()
        obj.published_by = request.user
        obj.save(update_fields=['is_published', 'published_at', 'published_by'])
        logger.info(f"LandingPage {pk} published by {request.user}")
        return Response({'status': 'published', 'published_at': obj.published_at})

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a landing page."""
        obj = self.get_object()
        new_title = request.data.get('title', f'{obj.title} (Copy)')
        obj.pk = None
        obj.title = new_title
        obj.slug = f'{obj.slug}-copy'
        obj.is_published = False
        obj.published_at = None
        obj.created_by = request.user
        obj.save()
        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Return analytics for this landing page."""
        obj = self.get_object()
        return Response({
            'landing_page_id': obj.id,
            'view_count': getattr(obj, 'view_count', 0),
            'conversion_count': getattr(obj, 'conversion_count', 0),
            'conversion_rate': getattr(obj, 'conversion_rate', 0.0),
        })
