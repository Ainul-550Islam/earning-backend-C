"""
api/offerwall/content_lock.py

Content Locking — gate any URL behind an offer completion.
Mirrors CPAlead / OGAds content-gate feature.

Usage:
    POST /api/offerwall/locks/            → create a gate (publisher)
    GET  /api/offerwall/locks/{token}/    → check if unlocked
    POST /api/offerwall/locks/{token}/unlock/ → mark unlocked after conversion
"""
import uuid
import hashlib
import logging
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────

class ContentLock(models.Model):
    """
    A content gate that requires completing ≥1 offer to unlock.

    Publishers embed the lock token in a redirect URL.
    Once the required number of conversions exist, the gate opens.
    """

    LOCK_TYPES = (
        ('url',       'URL redirect'),
        ('download',  'File download'),
        ('text',      'Hidden text'),
        ('video',     'Video unlock'),
        ('page',      'Page section'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Publisher / tenant
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='offerwall_content_locks',
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='offerwall_content_locks',
    )

    # What is gated
    lock_type  = models.CharField(max_length=20, choices=LOCK_TYPES, default='url')
    title      = models.CharField(max_length=300)
    description= models.TextField(blank=True)

    # The content revealed after unlock
    content_url     = models.URLField(max_length=2000, blank=True)
    content_text    = models.TextField(blank=True)
    content_file    = models.URLField(max_length=2000, blank=True)

    # Unlock requirements
    required_conversions = models.PositiveIntegerField(
        default=1,
        help_text='How many offer completions unlock this gate',
    )
    min_payout_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('0'),
        help_text='Minimum total payout required (0 = any)',
    )

    # Offer filter (optional — restrict which offers count)
    allowed_offer_types = models.JSONField(
        default=list, blank=True,
        help_text='Empty = all types allowed',
    )

    # Access token (shown to end-users)
    token = models.CharField(max_length=64, unique=True, db_index=True)

    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)

    # Stats
    total_views   = models.PositiveIntegerField(default=0)
    total_unlocks = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token'],              name='idx_cl_token'),
            models.Index(fields=['publisher', 'is_active'], name='idx_cl_pub_active'),
        ]
        verbose_name = 'Content lock'
        verbose_name_plural = 'Content locks'

    def __str__(self):
        return f'{self.title} [{self.lock_type}]'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self._generate_token()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_token():
        raw = f'{uuid.uuid4()}{timezone.now().isoformat()}'
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def is_unlocked_for(self, user):
        """Check whether `user` has completed enough offers."""
        if not user or not user.is_authenticated:
            return False

        from api.offerwall.models import OfferConversion
        qs = OfferConversion.objects.filter(
            user=user, status='approved',
        )
        if self.allowed_offer_types:
            qs = qs.filter(offer__offer_type__in=self.allowed_offer_types)
        if self.min_payout_usd > 0:
            from django.db.models import Sum
            total = qs.aggregate(t=Sum('payout_amount'))['t'] or Decimal('0')
            if total < self.min_payout_usd:
                return False
        return qs.count() >= self.required_conversions


class ContentLockAccess(models.Model):
    """Tracks each successful unlock by a user."""
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lock        = models.ForeignKey(ContentLock, on_delete=models.CASCADE, related_name='accesses')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='offerwall_lock_accesses')
    accessed_at = models.DateTimeField(auto_now_add=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = ['lock', 'user']
        ordering = ['-accessed_at']


# ─────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────

class ContentLockSerializer(serializers.ModelSerializer):
    is_expired = serializers.SerializerMethodField()
    is_unlocked = serializers.SerializerMethodField()

    class Meta:
        model = ContentLock
        fields = [
            'id', 'lock_type', 'title', 'description',
            'required_conversions', 'min_payout_usd',
            'allowed_offer_types', 'token',
            'expires_at', 'total_views', 'total_unlocks',
            'is_active', 'is_expired', 'is_unlocked',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'token', 'total_views', 'total_unlocks',
                            'is_expired', 'is_unlocked', 'created_at', 'updated_at']

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_is_unlocked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_unlocked_for(request.user)
        return False


class ContentLockCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentLock
        fields = [
            'lock_type', 'title', 'description',
            'content_url', 'content_text', 'content_file',
            'required_conversions', 'min_payout_usd',
            'allowed_offer_types', 'expires_at',
        ]


class ContentLockPublicSerializer(serializers.ModelSerializer):
    """Safe subset for unauthenticated viewers (no content revealed)."""
    is_expired  = serializers.SerializerMethodField()
    is_unlocked = serializers.SerializerMethodField()

    class Meta:
        model = ContentLock
        fields = [
            'id', 'lock_type', 'title', 'description',
            'required_conversions', 'token',
            'is_expired', 'is_unlocked',
        ]

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_is_unlocked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_unlocked_for(request.user)
        return False


# ─────────────────────────────────────────────────────────────
# ViewSet
# ─────────────────────────────────────────────────────────────

class ContentLockViewSet(viewsets.ModelViewSet):
    """
    CRUD for content locks (publishers).

    GET    /api/offerwall/locks/                   list own locks
    POST   /api/offerwall/locks/                   create lock
    GET    /api/offerwall/locks/{id}/              lock detail
    GET    /api/offerwall/locks/{id}/check/        check unlock status
    POST   /api/offerwall/locks/{id}/unlock/       record unlock access
    GET    /api/offerwall/locks/by_token/{token}/  public lookup by token
    """

    permission_classes = [IsAuthenticated]
    serializer_class   = ContentLockSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return ContentLock.objects.all()
        return ContentLock.objects.filter(publisher=self.request.user)

    def create(self, request, *args, **kwargs):
        """Override create to enforce B2B plan gate (allow_content_lock)."""
        if hasattr(request.user, 'b2b_client'):
            client = request.user.b2b_client
            if not client.has_feature('content_lock'):
                from rest_framework.response import Response
                return Response(
                    {'error': 'plan_limit',
                     'detail': 'Content locking requires Starter plan or above.',
                     'upgrade_url': '/api/offerwall/b2b/upgrade/'},
                    status=403)
        return super().create(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'create':
            return ContentLockCreateSerializer
        return ContentLockSerializer

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)

    # ── check unlock ──────────────────────────────────────────
    @action(detail=True, methods=['get'])
    def check(self, request, pk=None):
        """Check if current user has unlocked this gate."""
        lock = self.get_object()

        if lock.is_expired():
            return Response({'unlocked': False, 'reason': 'expired'},
                            status=status.HTTP_410_GONE)

        unlocked = lock.is_unlocked_for(request.user)

        # Increment view counter
        ContentLock.objects.filter(pk=lock.pk).update(total_views=models.F('total_views') + 1)

        if unlocked:
            return Response({
                'unlocked': True,
                'lock_type': lock.lock_type,
                'content_url':  lock.content_url  if lock.lock_type in ('url', 'download') else None,
                'content_text': lock.content_text if lock.lock_type == 'text'              else None,
            })

        return Response({
            'unlocked': False,
            'required_conversions': lock.required_conversions,
            'reason': 'insufficient_conversions',
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    # ── record unlock access ──────────────────────────────────
    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """Record that user unlocked this gate; return content."""
        lock = self.get_object()

        if not lock.is_unlocked_for(request.user):
            return Response({'error': 'not_unlocked'}, status=status.HTTP_403_FORBIDDEN)

        access, created = ContentLockAccess.objects.get_or_create(
            lock=lock, user=request.user,
            defaults={'ip_address': request.META.get('REMOTE_ADDR')},
        )
        if created:
            ContentLock.objects.filter(pk=lock.pk).update(
                total_unlocks=models.F('total_unlocks') + 1)

        return Response({
            'unlocked': True,
            'lock_type': lock.lock_type,
            'content_url':  lock.content_url  or None,
            'content_text': lock.content_text or None,
            'content_file': lock.content_file or None,
            'accessed_at':  access.accessed_at,
        })

    # ── public by-token lookup ────────────────────────────────
    @action(detail=False, methods=['get'], url_path='by_token/(?P<token>[^/.]+)',
            permission_classes=[AllowAny])
    def by_token(self, request, token=None):
        """Public endpoint — look up a lock by its short token."""
        try:
            lock = ContentLock.objects.get(token=token, is_active=True)
        except ContentLock.DoesNotExist:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ContentLockPublicSerializer(lock, context={'request': request})
        return Response(serializer.data)
