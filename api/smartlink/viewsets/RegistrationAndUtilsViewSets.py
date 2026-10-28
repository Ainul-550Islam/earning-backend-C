"""
SmartLink Publisher Self-Serve + Utility ViewSets

1. RegistrationViewSet  — publisher self-serve signup, email verification, KYC admin review
2. QRCodeView           — generate QR code PNG for any SmartLink
3. UTMBuilderView       — build and save UTM-tagged SmartLink URLs
4. DeepLinkViewSet      — manage iOS/Android universal link config per SmartLink
"""
import logging
import io
import base64
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import serializers

User = get_user_model()
logger = logging.getLogger('smartlink.viewsets.registration')


# ─────────────────────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────────────────────

class PublisherRegistrationSerializer(serializers.Serializer):
    """Input for /register/ endpoint."""
    username        = serializers.CharField(max_length=150, min_length=3)
    email           = serializers.EmailField()
    password        = serializers.CharField(min_length=8, write_only=True)
    password_confirm = serializers.CharField(min_length=8, write_only=True)
    company_name    = serializers.CharField(max_length=200, required=False, allow_blank=True)
    website         = serializers.URLField(required=False, allow_blank=True)
    vertical        = serializers.CharField(max_length=100, required=False, allow_blank=True)
    traffic_sources = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )
    gdpr_consent    = serializers.BooleanField()

    def validate_gdpr_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                'GDPR consent is required to create an account.'
            )
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        if not value.replace('_', '').replace('-', '').isalnum():
            raise serializers.ValidationError(
                'Username may only contain letters, numbers, hyphens, and underscores.'
            )
        return value.lower()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email address is already registered.')
        return value.lower()

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=128)


class KYCReviewSerializer(serializers.Serializer):
    """Admin KYC approval/rejection input."""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    note   = serializers.CharField(max_length=500, required=False, allow_blank=True)


class UTMBuilderSerializer(serializers.Serializer):
    """Build a UTM-tagged URL for a SmartLink."""
    slug         = serializers.SlugField()
    utm_source   = serializers.CharField(max_length=200)
    utm_medium   = serializers.CharField(max_length=200)
    utm_campaign = serializers.CharField(max_length=200)
    utm_content  = serializers.CharField(max_length=200, required=False, allow_blank=True)
    utm_term     = serializers.CharField(max_length=200, required=False, allow_blank=True)
    save         = serializers.BooleanField(
        default=False,
        help_text='If true, save this UTM set to the SmartLink for analytics tracking.',
    )


class DeepLinkConfigSerializer(serializers.Serializer):
    """Universal link / deep link configuration per SmartLink."""
    android_url     = serializers.URLField(
        required=False, allow_blank=True,
        help_text='Android intent URL or Play Store URL.',
    )
    ios_url         = serializers.URLField(
        required=False, allow_blank=True,
        help_text='iOS Universal Link or App Store URL.',
    )
    fallback_url    = serializers.URLField(
        required=False, allow_blank=True,
        help_text='Fallback web URL for unsupported devices.',
    )
    enable_smart_routing = serializers.BooleanField(
        default=True,
        help_text='Auto-detect device and route to correct store URL.',
    )
    bundle_id       = serializers.CharField(
        max_length=200, required=False, allow_blank=True,
        help_text='iOS bundle ID for Universal Link verification.',
    )
    package_name    = serializers.CharField(
        max_length=200, required=False, allow_blank=True,
        help_text='Android package name for App Link verification.',
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. RegistrationViewSet
# ─────────────────────────────────────────────────────────────────────────────

class RegistrationViewSet(viewsets.ViewSet):
    """
    Publisher self-serve registration and KYC workflow.

    Public:
      POST /api/smartlink/register/             — register new publisher account
      POST /api/smartlink/register/verify-email/ — verify email token
      GET  /api/smartlink/register/resend-verification/ — resend verification email

    Publisher (authenticated):
      POST /api/smartlink/register/submit-kyc/  — submit KYC documents
      GET  /api/smartlink/register/kyc-status/  — check KYC status

    Admin:
      GET  /api/smartlink/admin/kyc-queue/      — list pending KYC applications
      POST /api/smartlink/admin/kyc-queue/{id}/review/ — approve or reject
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='register',
            permission_classes=[AllowAny])
    def register(self, request):
        """
        POST /api/smartlink/register/
        Create a new publisher account. Sends verification email.
        Account is inactive until email is verified.
        KYC approval unlocks full platform access.
        """
        serializer = PublisherRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Create user (inactive until email verified)
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            is_active=False,
        )

        # Create publisher profile
        from api.smartlink.models.billing import PublisherProfile
        profile = PublisherProfile.objects.create(
            publisher=user,
            company_name=data.get('company_name', ''),
            website=data.get('website', ''),
            vertical=data.get('vertical', ''),
            traffic_sources=data.get('traffic_sources', []),
            gdpr_consent=True,
            gdpr_consent_at=timezone.now(),
        )

        # Create wallet
        from api.smartlink.models.billing import PublisherWallet
        PublisherWallet.objects.create(publisher=user)

        # Create Standard tier
        from api.smartlink.models.extensions.smartlink_schedule import PublisherTier
        PublisherTier.objects.create(
            publisher=user,
            tier='standard',
            max_smartlinks=10,
            max_custom_domains=1,
            api_rate_limit=500,
            can_use_ml_rotation=False,
            can_use_ab_testing=False,
            can_use_pre_landers=False,
            payout_bonus_percent=0,
        )

        # Generate + cache email verification token
        import secrets
        token = secrets.token_urlsafe(48)
        from django.core.cache import cache
        cache.set(
            f'email_verify:{token}',
            {'user_id': user.pk, 'email': user.email},
            timeout=86400,  # 24 hours
        )

        # Send verification email
        try:
            from api.smartlink.services.notification.NotificationService import NotificationService
            NotificationService()._send_email(
                user=user,
                subject='Verify your SmartLink account',
                message=(
                    f"Welcome {user.username}!\n\n"
                    f"Click the link below to verify your email:\n"
                    f"{request.build_absolute_uri('/api/smartlink/register/verify-email/')}?token={token}\n\n"
                    f"This link expires in 24 hours."
                ),
            )
        except Exception as e:
            logger.error(f"Verification email failed for {user.email}: {e}")

        logger.info(f"Publisher registered: {user.username} ({user.email})")
        return Response({
            'message': 'Account created. Check your email to verify your address.',
            'username': user.username,
            'email': user.email,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='verify-email',
            permission_classes=[AllowAny])
    def verify_email(self, request):
        """
        POST /api/smartlink/register/verify-email/
        Body: {"token": "..."} or GET ?token=...
        Activate publisher account after email verification.
        """
        token = (
            request.data.get('token')
            or request.query_params.get('token', '')
        )
        if not token:
            return Response({'detail': 'token is required.'}, status=400)

        from django.core.cache import cache
        data = cache.get(f'email_verify:{token}')
        if not data:
            return Response(
                {'detail': 'Invalid or expired verification token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=data['user_id'], email=data['email'])
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=400)

        user.is_active = True
        user.save(update_fields=['is_active'])
        cache.delete(f'email_verify:{token}')

        logger.info(f"Email verified: {user.username}")
        return Response({'message': 'Email verified. You can now log in.'})

    @action(detail=False, methods=['post'], url_path='submit-kyc',
            permission_classes=[IsAuthenticated])
    def submit_kyc(self, request):
        """
        POST /api/smartlink/register/submit-kyc/
        Publisher submits KYC information for admin review.
        Body: {company_name, tax_id, website, traffic_volume_per_day, notes}
        """
        from api.smartlink.models.billing import PublisherProfile
        profile, _ = PublisherProfile.objects.get_or_create(publisher=request.user)

        fields_to_update = {}
        for field in ('company_name', 'tax_id', 'website', 'vertical', 'traffic_sources'):
            if field in request.data:
                fields_to_update[field] = request.data[field]

        if fields_to_update:
            for k, v in fields_to_update.items():
                setattr(profile, k, v)
            profile.save()

        # Notify admin
        try:
            admin_emails = list(
                User.objects.filter(is_staff=True).values_list('email', flat=True)
            )
            if admin_emails:
                from api.smartlink.services.notification.NotificationService import NotificationService
                for admin_email in admin_emails[:3]:  # max 3 admins
                    from api.smartlink.services.notification.NotificationService import NotificationService
                    NotificationService()._send_email(
                        user=User.objects.filter(is_staff=True).first(),
                        subject=f'New KYC submission: {request.user.username}',
                        message=(
                            f"Publisher {request.user.username} has submitted KYC documents.\n"
                            f"Review at: /admin/kyc-queue/"
                        ),
                    )
        except Exception as e:
            logger.warning(f"KYC admin notification failed: {e}")

        return Response({'message': 'KYC information submitted. Admin review in progress.'})

    @action(detail=False, methods=['get'], url_path='kyc-status',
            permission_classes=[IsAuthenticated])
    def kyc_status(self, request):
        """GET /api/smartlink/register/kyc-status/ — publisher's own KYC status."""
        from api.smartlink.models.billing import PublisherProfile
        try:
            profile = request.user.publisher_profile
            return Response({
                'is_verified': profile.is_verified,
                'verified_at': profile.verified_at,
                'data_anonymized': profile.data_anonymized,
                'message': (
                    'Account verified.' if profile.is_verified
                    else 'Pending admin review. Usually takes 24–48 hours.'
                ),
            })
        except PublisherProfile.DoesNotExist:
            return Response({'is_verified': False, 'message': 'Profile not set up yet.'})

    # ── Admin KYC queue ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='admin-kyc-queue',
            permission_classes=[IsAuthenticated])
    def admin_kyc_queue(self, request):
        """GET /api/smartlink/register/admin-kyc-queue/ — list pending KYC (admin only)."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=403)

        from api.smartlink.models.billing import PublisherProfile
        pending = PublisherProfile.objects.filter(
            is_verified=False,
            data_anonymized=False,
        ).select_related('publisher').order_by('-created_at')

        return Response([{
            'user_id': p.publisher_id,
            'username': p.publisher.username,
            'email': p.publisher.email,
            'company_name': p.company_name,
            'website': p.website,
            'vertical': p.vertical,
            'tax_id': bool(p.tax_id),  # don't expose raw tax ID
            'gdpr_consent': p.gdpr_consent,
            'created_at': p.created_at,
        } for p in pending[:100]])

    @action(detail=False, methods=['post'],
            url_path=r'admin-kyc-review/(?P<user_pk>[^/.]+)',
            permission_classes=[IsAuthenticated])
    def admin_kyc_review(self, request, user_pk=None):
        """
        POST /api/smartlink/register/admin-kyc-review/{user_pk}/
        Admin: approve or reject KYC application.
        Body: {"action": "approve" | "reject", "note": "..."}
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=403)

        serializer = KYCReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_val = serializer.validated_data['action']
        note = serializer.validated_data.get('note', '')

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)

        from api.smartlink.models.billing import PublisherProfile
        profile, _ = PublisherProfile.objects.get_or_create(publisher=user)

        if action_val == 'approve':
            from api.smartlink.models.billing import PublisherProfile as PP
            PP.objects.filter(pk=profile.pk).update(
                is_verified=True,
                verified_at=timezone.now(),
                notes=f"Approved by {request.user.username}. {note}".strip(),
            )
            logger.info(f"KYC approved: {user.username} by {request.user.username}")
            msg = f'{user.username} verified.'

        else:  # reject
            PP = PublisherProfile
            PP.objects.filter(pk=profile.pk).update(
                notes=f"Rejected by {request.user.username}. {note}".strip(),
            )
            logger.info(f"KYC rejected: {user.username} by {request.user.username}")
            msg = f'{user.username} rejected.'

        # Notify publisher
        try:
            from api.smartlink.services.notification.NotificationService import NotificationService
            NotificationService()._send_email(
                user=user,
                subject='SmartLink — Account review update',
                message=(
                    f"Your account has been {'approved' if action_val == 'approve' else 'rejected'}.\n"
                    + (f"\nNote from admin: {note}" if note else '')
                ),
            )
        except Exception as e:
            logger.warning(f"KYC notification failed: {e}")

        return Response({'message': msg})


# ─────────────────────────────────────────────────────────────────────────────
# 2. QRCodeView
# ─────────────────────────────────────────────────────────────────────────────

class QRCodeView(APIView):
    """
    Generate QR code for a SmartLink.

    GET /api/smartlink/smartlinks/{slug}/qr/
        ?format=png|svg|base64   (default: png)
        ?size=200                (px, default: 200, max: 1000)
        ?error_correction=M      (L/M/Q/H, default: M)

    Returns PNG image (Content-Type: image/png) or SVG or JSON with base64.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404

        if request.user.is_staff:
            sl = get_object_or_404(SmartLink, slug=slug)
        else:
            sl = get_object_or_404(SmartLink, slug=slug, publisher=request.user)

        fmt            = request.query_params.get('format', 'png').lower()
        size           = min(int(request.query_params.get('size', 200)), 1000)
        error_level    = request.query_params.get('error_correction', 'M').upper()
        full_url       = sl.full_url

        try:
            import qrcode
            from qrcode.constants import (
                ERROR_CORRECT_L, ERROR_CORRECT_M,
                ERROR_CORRECT_Q, ERROR_CORRECT_H,
            )
            ec_map = {
                'L': ERROR_CORRECT_L,
                'M': ERROR_CORRECT_M,
                'Q': ERROR_CORRECT_Q,
                'H': ERROR_CORRECT_H,
            }
            qr = qrcode.QRCode(
                version=None,
                error_correction=ec_map.get(error_level, ERROR_CORRECT_M),
                box_size=10,
                border=4,
            )
            qr.add_data(full_url)
            qr.make(fit=True)

            if fmt == 'svg':
                import qrcode.image.svg
                factory = qrcode.image.svg.SvgImage
                img = qr.make_image(image_factory=factory)
                buffer = io.BytesIO()
                img.save(buffer)
                return Response(
                    buffer.getvalue().decode(),
                    content_type='image/svg+xml',
                    headers={
                        'Content-Disposition': f'inline; filename="qr_{slug}.svg"',
                    },
                )

            img = qr.make_image(fill_color='black', back_color='white')
            # Resize if requested
            if size != 200:
                img = img.resize((size, size))

            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            if fmt == 'base64':
                encoded = base64.b64encode(buffer.getvalue()).decode()
                return Response({
                    'slug': slug,
                    'url': full_url,
                    'format': 'base64',
                    'data': f'data:image/png;base64,{encoded}',
                    'size': size,
                })

            return Response(
                buffer.getvalue(),
                content_type='image/png',
                headers={
                    'Content-Disposition': f'inline; filename="qr_{slug}.png"',
                    'Cache-Control': 'public, max-age=3600',
                },
            )

        except ImportError:
            return Response(
                {
                    'detail': (
                        'qrcode library not installed. '
                        'Run: pip install qrcode[pil]'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.error(f"QR code generation failed for [{slug}]: {e}")
            return Response(
                {'detail': f'QR generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3. UTMBuilderView
# ─────────────────────────────────────────────────────────────────────────────

class UTMBuilderView(APIView):
    """
    Build UTM-tagged SmartLink URLs.

    POST /api/smartlink/utm/build/
    Body: {slug, utm_source, utm_medium, utm_campaign, utm_content?, utm_term?, save?}

    Returns the full tagged URL. If save=true, persists UTM preset to SmartLink config.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UTMBuilderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        from urllib.parse import urlencode

        if request.user.is_staff:
            sl = get_object_or_404(SmartLink, slug=data['slug'])
        else:
            sl = get_object_or_404(
                SmartLink, slug=data['slug'], publisher=request.user
            )

        # Build UTM params
        utm_params = {
            'utm_source':   data['utm_source'],
            'utm_medium':   data['utm_medium'],
            'utm_campaign': data['utm_campaign'],
        }
        if data.get('utm_content'):
            utm_params['utm_content'] = data['utm_content']
        if data.get('utm_term'):
            utm_params['utm_term'] = data['utm_term']

        base_url = sl.full_url
        separator = '&' if '?' in base_url else '?'
        tagged_url = f"{base_url}{separator}{urlencode(utm_params)}"

        # Optionally save this UTM preset to the SmartLink
        if data.get('save'):
            try:
                existing = getattr(sl, 'utm_presets', None)
                config = sl.__dict__.get('integrations', {}) or {}
                utm_presets = config.get('utm_presets', [])
                preset_name = f"{data['utm_source']}/{data['utm_medium']}/{data['utm_campaign']}"
                utm_presets.append({
                    'name': preset_name,
                    'params': utm_params,
                    'url': tagged_url,
                    'created_at': timezone.now().isoformat(),
                })
                config['utm_presets'] = utm_presets[-20:]  # keep last 20
                SmartLink.objects.filter(pk=sl.pk).update(integrations=config)
                logger.info(f"UTM preset saved for [{sl.slug}]: {preset_name}")
            except Exception as e:
                logger.warning(f"UTM preset save failed: {e}")

        return Response({
            'slug':        data['slug'],
            'base_url':    base_url,
            'utm_params':  utm_params,
            'tagged_url':  tagged_url,
            'saved':       data.get('save', False),
        })

    def get(self, request):
        """
        GET /api/smartlink/utm/build/?slug=abc
        Return saved UTM presets for a SmartLink.
        """
        slug = request.query_params.get('slug', '')
        if not slug:
            return Response({'detail': 'slug query param required.'}, status=400)

        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        if request.user.is_staff:
            sl = get_object_or_404(SmartLink, slug=slug)
        else:
            sl = get_object_or_404(SmartLink, slug=slug, publisher=request.user)

        config = sl.__dict__.get('integrations', {}) or {}
        presets = config.get('utm_presets', [])
        return Response({'slug': slug, 'presets': presets})


# ─────────────────────────────────────────────────────────────────────────────
# 4. DeepLinkViewSet
# ─────────────────────────────────────────────────────────────────────────────

class DeepLinkViewSet(viewsets.ViewSet):
    """
    Manage iOS/Android Universal Link configuration per SmartLink.

    GET    /api/smartlink/smartlinks/{slug}/deep-link/        — current config
    PUT    /api/smartlink/smartlinks/{slug}/deep-link/        — save config
    DELETE /api/smartlink/smartlinks/{slug}/deep-link/        — remove config
    GET    /api/smartlink/smartlinks/{slug}/deep-link/test/   — test routing logic
    GET    /.well-known/assetlinks.json                       — Android verification
    GET    /.well-known/apple-app-site-association            — iOS verification
    """
    permission_classes = [IsAuthenticated]

    def _get_sl(self, request, slug):
        from api.smartlink.models import SmartLink
        from django.shortcuts import get_object_or_404
        if request.user.is_staff:
            return get_object_or_404(SmartLink, slug=slug)
        return get_object_or_404(SmartLink, slug=slug, publisher=request.user)

    def retrieve(self, request, slug=None):
        """GET /api/smartlink/smartlinks/{slug}/deep-link/"""
        sl = self._get_sl(request, slug)
        integrations = getattr(sl, 'integrations', {}) or {}
        config = integrations.get('deep_link', {})
        return Response({'slug': slug, 'deep_link': config})

    def update(self, request, slug=None):
        """PUT /api/smartlink/smartlinks/{slug}/deep-link/"""
        from api.smartlink.models import SmartLink
        sl = self._get_sl(request, slug)
        serializer = DeepLinkConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        integrations = getattr(sl, 'integrations', {}) or {}
        integrations['deep_link'] = serializer.validated_data
        SmartLink.objects.filter(pk=sl.pk).update(integrations=integrations)

        logger.info(f"Deep link config updated for [{slug}] by {request.user.username}")
        return Response({'slug': slug, 'deep_link': serializer.validated_data})

    def destroy(self, request, slug=None):
        """DELETE /api/smartlink/smartlinks/{slug}/deep-link/"""
        from api.smartlink.models import SmartLink
        sl = self._get_sl(request, slug)
        integrations = getattr(sl, 'integrations', {}) or {}
        integrations.pop('deep_link', None)
        SmartLink.objects.filter(pk=sl.pk).update(integrations=integrations)
        return Response({'message': 'Deep link configuration removed.'})

    @action(detail=True, methods=['get'], url_path='test')
    def test_routing(self, request, slug=None):
        """
        GET /api/smartlink/smartlinks/{slug}/deep-link/test/?ua=Mozilla...
        Simulate deep link routing for a given User-Agent.
        """
        sl = self._get_sl(request, slug)
        integrations = getattr(sl, 'integrations', {}) or {}
        config = integrations.get('deep_link', {})
        if not config:
            return Response({'detail': 'No deep link config set.'}, status=404)

        ua = request.query_params.get('ua', request.META.get('HTTP_USER_AGENT', ''))
        ua_lower = ua.lower()

        if 'iphone' in ua_lower or 'ipad' in ua_lower or 'ios' in ua_lower:
            platform = 'ios'
            target_url = config.get('ios_url') or config.get('fallback_url') or sl.full_url
        elif 'android' in ua_lower:
            platform = 'android'
            target_url = config.get('android_url') or config.get('fallback_url') or sl.full_url
        else:
            platform = 'web'
            target_url = config.get('fallback_url') or sl.full_url

        return Response({
            'slug': slug,
            'detected_platform': platform,
            'target_url': target_url,
            'config': config,
            'user_agent': ua[:200],
        })
