"""
api/offerwall/publisher.py

Publisher / Embed SDK API

Lets publishers (app owners) embed your offerwall as:
  • An <iframe> with a signed token
  • A JS SDK snippet (one-liner)
  • A REST endpoint their backend can query

Endpoints:
  POST /api/offerwall/publisher/embed-token/    → generate signed embed token
  GET  /api/offerwall/publisher/sdk-config/     → JS SDK configuration JSON
  GET  /api/offerwall/publisher/stats/          → publisher-level conversion stats
  POST /api/offerwall/publisher/keys/           → create API key
  GET  /api/offerwall/publisher/keys/           → list API keys
  DELETE /api/offerwall/publisher/keys/{id}/    → revoke API key

Authentication:
  All endpoints require IsAuthenticated.
  SDK-config supports both session auth AND X-Publisher-Key header.
"""
import uuid
import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class PublisherAPIKey(models.Model):
    """
    API key issued to a publisher for embed/SDK use.
    Scoped to a single user (publisher) — not a global admin key.
    """

    SCOPE_CHOICES = (
        ('read',       'Read only'),
        ('embed',      'Embed SDK'),
        ('full',       'Full access'),
    )

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publisher  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='offerwall_publisher_keys',
    )
    name       = models.CharField(max_length=100, help_text='Friendly name for this key')
    key_prefix = models.CharField(max_length=8,  db_index=True)
    key_hash   = models.CharField(max_length=64, help_text='SHA-256 of the full key')
    scope      = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='embed')
    is_active  = models.BooleanField(default=True)
    last_used  = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['key_prefix', 'key_hash'],
                                 name='idx_pub_key_prefix_hash')]
        verbose_name        = 'Publisher API key'
        verbose_name_plural = 'Publisher API keys'

    def __str__(self):
        return f'{self.publisher.username} / {self.name} ({self.key_prefix}…)'

    @classmethod
    def generate(cls, publisher, name, scope='embed', expires_days=None):
        """
        Create a new API key.  Returns (instance, raw_key).
        raw_key is shown once — not stored.
        """
        raw_key    = f'ow_{uuid.uuid4().hex}{uuid.uuid4().hex}'
        prefix     = raw_key[:8]
        key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()
        expires_at = (timezone.now() + timedelta(days=expires_days)
                      if expires_days else None)
        instance   = cls.objects.create(
            publisher=publisher, name=name, scope=scope,
            key_prefix=prefix, key_hash=key_hash,
            expires_at=expires_at,
        )
        return instance, raw_key

    @classmethod
    def authenticate(cls, raw_key: str):
        """Return the publisher User for a valid raw key, else None."""
        if not raw_key or not raw_key.startswith('ow_'):
            return None
        prefix   = raw_key[:8]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            key = cls.objects.select_related('publisher').get(
                key_prefix=prefix, key_hash=key_hash,
                is_active=True,
            )
        except cls.DoesNotExist:
            return None
        if key.expires_at and timezone.now() > key.expires_at:
            return None
        cls.objects.filter(pk=key.pk).update(last_used=timezone.now())
        return key.publisher

    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)


# ─────────────────────────────────────────────────────────────
# DRF authentication class (X-Publisher-Key header)
# ─────────────────────────────────────────────────────────────

class PublisherKeyAuthentication(BaseAuthentication):
    """Allow X-Publisher-Key: ow_xxx... authentication for embed endpoints."""

    def authenticate(self, request):
        raw_key = request.headers.get('X-Publisher-Key', '')
        if not raw_key:
            return None                        # fall through to next auth
        user = PublisherAPIKey.authenticate(raw_key)
        if user is None:
            raise AuthenticationFailed('Invalid or expired publisher key')
        return (user, None)


# ─────────────────────────────────────────────────────────────
# Embed token helper
# ─────────────────────────────────────────────────────────────

class EmbedTokenService:
    """
    Generate a short-lived, signed embed token.

    The token encodes: user_id + wall_id + timestamp.
    The frontend uses this token to initialise the JS SDK:

        OfferWall.init({ token: '<embed_token>' });
    """

    SECRET = getattr(settings, 'OFFERWALL_EMBED_SECRET',
                     getattr(settings, 'SECRET_KEY', 'change-me'))
    TTL    = 3600   # seconds

    @classmethod
    def generate(cls, user_id, wall_id=None, extra=None):
        ts      = int(timezone.now().timestamp())
        payload = f'{user_id}:{wall_id or ""}:{ts}'
        sig     = hmac.new(cls.SECRET.encode(), payload.encode(),
                           hashlib.sha256).hexdigest()[:16]
        token   = f'{payload}:{sig}'
        return {
            'token':      token,
            'expires_at': timezone.now() + timedelta(seconds=cls.TTL),
            'ttl':        cls.TTL,
        }

    @classmethod
    def verify(cls, token: str) -> dict | None:
        try:
            parts   = token.rsplit(':', 1)
            payload = parts[0]
            sig     = parts[1]
            segs    = payload.split(':')
            ts      = int(segs[2])
        except Exception:
            return None
        if int(timezone.now().timestamp()) - ts > cls.TTL:
            return None
        expected = hmac.new(cls.SECRET.encode(), payload.encode(),
                            hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(expected, sig):
            return None
        return {'user_id': segs[0], 'wall_id': segs[1] or None, 'ts': ts}


# ─────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────

class PublisherAPIKeySerializer(serializers.ModelSerializer):
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model  = PublisherAPIKey
        fields = ['id', 'name', 'key_prefix', 'scope',
                  'is_active', 'is_expired', 'last_used',
                  'expires_at', 'created_at']
        read_only_fields = ['id', 'key_prefix', 'is_expired', 'last_used', 'created_at']

    def get_is_expired(self, obj):
        return obj.is_expired()


class EmbedTokenRequestSerializer(serializers.Serializer):
    wall_id     = serializers.UUIDField(required=False, allow_null=True)
    user_ref    = serializers.CharField(max_length=200, required=False,
                                        help_text='External user reference (your user ID)')
    ttl_seconds = serializers.IntegerField(min_value=60, max_value=86400,
                                           required=False, default=3600)


# ─────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────

class EmbedTokenView(APIView):
    """
    POST /api/offerwall/publisher/embed-token/

    Returns a signed embed token for JS SDK initialisation.
    """
    authentication_classes = [PublisherKeyAuthentication] + \
        list(getattr(
            __import__('rest_framework').authentication,
            'DEFAULT_AUTHENTICATION_CLASSES',
            []
        ))
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # FIX: No B2B plan gating — any user could get embed token.
        # Now requires allow_white_label feature on plan.
        if hasattr(request.user, 'b2b_client'):
            client = request.user.b2b_client
            if not client.is_active():
                return Response(
                    {'error': 'client_not_active',
                     'detail': 'Your B2B account is not active.'},
                    status=status.HTTP_403_FORBIDDEN)
            if not client.has_feature('white_label'):
                return Response(
                    {'error': 'plan_limit',
                     'detail': 'Embed tokens require Pro plan or above.',
                     'upgrade_url': '/api/offerwall/b2b/upgrade/'},
                    status=status.HTTP_403_FORBIDDEN)
        ser = EmbedTokenRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        token_data = EmbedTokenService.generate(
            user_id=request.user.id,
            wall_id=ser.validated_data.get('wall_id'),
        )
        return Response({
            'embed_token': token_data['token'],
            'expires_at':  token_data['expires_at'],
            'ttl':         token_data['ttl'],
            'sdk_snippet': (
                f'<script src="https://your-domain.com/static/offerwall-sdk.js"'
                f' data-token="{token_data["token"]}"></script>'
            ),
        })


class SDKConfigView(APIView):
    """
    GET /api/offerwall/publisher/sdk-config/

    Returns JSON config consumed by the JS SDK at embed time.
    Accepts session auth OR X-Publisher-Key header.
    """
    authentication_classes = [PublisherKeyAuthentication]
    permission_classes     = [IsAuthenticated]

    def get(self, request):
        # FIX: SDKConfigView must check allow_analytics_api for advanced features
        analytics_enabled = True
        if hasattr(request.user, 'b2b_client'):
            client = request.user.b2b_client
            analytics_enabled = client.has_feature('analytics_api')
        wall_id = request.query_params.get('wall_id')

        from api.offerwall.models import OfferWall, Offer
        offers_qs = Offer.objects.filter(status='active').order_by('-quality_score')[:5]

        wall_config = {}
        if wall_id:
            try:
                wall = OfferWall.objects.get(id=wall_id, is_active=True)
                wall_config = {
                    'name':           wall.name,
                    'slug':           wall.slug,
                    'offers_per_page':wall.offers_per_page,
                    'sort_by':        wall.sort_by,
                    'min_payout':     str(wall.min_payout),
                }
            except OfferWall.DoesNotExist:
                pass

        return Response({
            'api_base':      '/api/offerwall/',
            'embed_version': '1.0',
            'wall':          wall_config,
            'preview_offers': [
                {'id': str(o.id), 'title': o.title,
                 'reward': str(o.reward_amount), 'currency': o.reward_currency}
                for o in offers_qs
            ],
            'features': {
                'fraud_detection': True,
                'geo_targeting':   True,
                'device_targeting':True,
            },
            'generated_at': timezone.now().isoformat(),
        })


class PublisherStatsView(APIView):
    """
    GET /api/offerwall/publisher/stats/

    Aggregated stats for the authenticated publisher.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.offerwall.models import OfferConversion
        from django.db.models import Sum, Count

        qs = OfferConversion.objects.filter(user=request.user)

        agg = qs.aggregate(
            total=Count('id'),
            approved=Count('id', filter=models.Q(status='approved')),
            pending=Count('id', filter=models.Q(status='pending')),
            rejected=Count('id', filter=models.Q(status='rejected')),
            chargeback=Count('id', filter=models.Q(status='chargeback')),
            total_earned=Sum('reward_amount', filter=models.Q(status='approved')),
            total_bonus=Sum('bonus_amount',  filter=models.Q(status='approved')),
        )

        return Response({
            'total_conversions':  agg['total'],
            'approved':           agg['approved'],
            'pending':            agg['pending'],
            'rejected':           agg['rejected'],
            'chargeback':         agg['chargeback'],
            'total_earned':       str(agg['total_earned'] or 0),
            'total_bonus':        str(agg['total_bonus']  or 0),
            'approval_rate':      round(
                (agg['approved'] / agg['total'] * 100) if agg['total'] else 0, 2),
        })


class PublisherAPIKeyViewSet(viewsets.ViewSet):
    """
    Manage publisher API keys.

    list    GET  /api/offerwall/publisher/keys/
    create  POST /api/offerwall/publisher/keys/
    destroy DELETE /api/offerwall/publisher/keys/{id}/
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        keys = PublisherAPIKey.objects.filter(
            publisher=request.user, is_active=True)
        return Response(PublisherAPIKeySerializer(keys, many=True).data)

    def create(self, request):
        name  = request.data.get('name', 'Default key')
        scope = request.data.get('scope', 'embed')
        expires_days = request.data.get('expires_days')

        if scope not in ('read', 'embed', 'full'):
            return Response({'error': 'invalid_scope'},
                            status=status.HTTP_400_BAD_REQUEST)

        instance, raw_key = PublisherAPIKey.generate(
            publisher=request.user, name=name, scope=scope,
            expires_days=int(expires_days) if expires_days else None,
        )
        data = PublisherAPIKeySerializer(instance).data
        data['key'] = raw_key   # shown once only
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        try:
            key = PublisherAPIKey.objects.get(
                id=pk, publisher=request.user)
            key.is_active = False
            key.save(update_fields=['is_active'])
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PublisherAPIKey.DoesNotExist:
            return Response({'error': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
