from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/FinalViewSets.py
"""
Final missing ViewSets:
- TwoFactorViewSet    — 2FA setup/verify
- APIKeyViewSet       — per-user API key management
- SessionViewSet      — active session management
- LandingPageViewSet  — CPAlead gaming landing pages
- FastPayViewSet      — daily payout management
- CurrencyViewSet     — currency localization
- MCPViewSet          — MCP server control
- CommentViewSet      — threaded comments
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from .cms_viewset_base import CMSViewSetMixin, CMSSmallPagination, CMSWriteThrottle

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 2FA ViewSet
# ─────────────────────────────────────────────

class TwoFactorViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    POST /api/cms/2fa/setup/           — Begin 2FA setup (get QR code)
    POST /api/cms/2fa/confirm/         — Confirm with first token
    POST /api/cms/2fa/verify/          — Verify token (on login)
    POST /api/cms/2fa/disable/         — Disable 2FA
    GET  /api/cms/2fa/status/          — Check if 2FA enabled
    POST /api/cms/2fa/backup_codes/    — Generate backup codes
    POST /api/cms/2fa/use_backup/      — Use backup code
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [CMSWriteThrottle]

    @action(detail=False, methods=['post'])
    def setup(self, request):
        from api.cms.two_factor import TOTPService
        secret, uri = TOTPService.setup_2fa(request.user)
        # Generate QR code URL (using Google Charts API)
        import urllib.parse
        qr_url = f"https://chart.googleapis.com/chart?chs=200x200&chld=M|0&cht=qr&chl={urllib.parse.quote(uri)}"
        return Response({
            'secret': secret,
            'provisioning_uri': uri,
            'qr_code_url': qr_url,
            'instructions': 'Scan QR code with Google Authenticator or Authy, then confirm with a token.',
        })

    @action(detail=False, methods=['post'])
    def confirm(self, request):
        from api.cms.two_factor import TOTPService
        token = request.data.get('token', '').strip()
        if not token:
            return Response({'error': 'token required'}, status=400)
        success = TOTPService.confirm_setup(request.user, token)
        if success:
            return Response({'success': True, 'message': '2FA enabled successfully!'})
        return Response({'success': False, 'error': 'Invalid token or setup expired'},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def verify(self, request):
        from api.cms.two_factor import TOTPService
        token = request.data.get('token', '').strip()
        backup = request.data.get('backup_code', '').strip()
        if token:
            valid = TOTPService.verify_user_token(request.user, token)
        elif backup:
            valid = TOTPService.verify_backup_code(request.user, backup)
        else:
            return Response({'error': 'token or backup_code required'}, status=400)
        return Response({'valid': valid})

    @action(detail=False, methods=['post'])
    def disable(self, request):
        from api.cms.two_factor import TOTPService
        token = request.data.get('token', '').strip()
        if not token:
            return Response({'error': 'Current token required to disable 2FA'}, status=400)
        success = TOTPService.disable_2fa(request.user, token)
        if success:
            return Response({'success': True, 'message': '2FA disabled.'})
        return Response({'success': False, 'error': 'Invalid token'}, status=400)

    @action(detail=False, methods=['get'])
    def status(self, request):
        from api.cms.two_factor import TOTPService
        return Response({
            'enabled': TOTPService.is_enabled(request.user),
            'username': request.user.username,
        })

    @action(detail=False, methods=['post'])
    def backup_codes(self, request):
        from api.cms.two_factor import TOTPService
        # Require current token to regenerate codes
        token = request.data.get('token', '').strip()
        if not TOTPService.verify_user_token(request.user, token):
            return Response({'error': 'Current 2FA token required'}, status=403)
        codes = TOTPService.generate_backup_codes(request.user)
        return Response({
            'codes': codes,
            'warning': 'Save these codes securely. Each can only be used once.',
            'count': len(codes),
        })

    @action(detail=False, methods=['post'])
    def use_backup(self, request):
        from api.cms.two_factor import TOTPService
        code = request.data.get('code', '').strip().upper()
        valid = TOTPService.verify_backup_code(request.user, code)
        return Response({'valid': valid})


# ─────────────────────────────────────────────
# API Key ViewSet
# ─────────────────────────────────────────────

class APIKeyViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/api-keys/            — List my API keys
    POST /api/cms/api-keys/create/     — Create new key (returns raw key once)
    POST /api/cms/api-keys/{id}/revoke/ — Revoke a key
    GET  /api/cms/api-keys/scopes/     — List available scopes
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = CMSSmallPagination
    throttle_classes = [CMSWriteThrottle]

    @action(detail=False, methods=['get'])
    def list_keys(self, request):
        from api.cms.models_new.api_keys import APIKey
        keys = APIKey.objects.filter(user=request.user, is_active=True)
        return Response({
            'results': [{
                'id': k.id,
                'name': k.name,
                'prefix': k.key_prefix,
                'scope': k.scope,
                'last_used': k.last_used_at.isoformat() if k.last_used_at else None,
                'request_count': k.request_count,
                'expires_at': k.expires_at.isoformat() if k.expires_at else None,
                'created_at': k.created_at.isoformat(),
            } for k in keys],
            'count': keys.count(),
        })

    @action(detail=False, methods=['post'])
    def create_key(self, request):
        from api.cms.models_new.api_keys import APIKey
        name = request.data.get('name', '').strip()
        scope = request.data.get('scope', 'read')
        allowed_ips = request.data.get('allowed_ips', '')
        expires_days = request.data.get('expires_days')

        if not name:
            return Response({'error': 'name required'}, status=400)

        # Max 10 keys per user
        if APIKey.objects.filter(user=request.user, is_active=True).count() >= 10:
            return Response({'error': 'Maximum 10 API keys per user'}, status=400)

        expires_at = None
        if expires_days:
            from django.utils import timezone
            import datetime
            expires_at = timezone.now() + datetime.timedelta(days=int(expires_days))

        api_key, raw_key = APIKey.create_key(
            user=request.user, name=name, scope=scope,
            allowed_ips=allowed_ips, expires_at=expires_at,
        )
        return Response({
            'id': api_key.id,
            'name': api_key.name,
            'key': raw_key,  # Shown ONCE — user must save this
            'prefix': api_key.key_prefix,
            'scope': api_key.scope,
            'warning': 'This key will not be shown again. Save it securely.',
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        from api.cms.models_new.api_keys import APIKey
        try:
            key = APIKey.objects.get(id=pk, user=request.user, is_active=True)
            key.revoke()
            return Response({'success': True, 'revoked': key.name})
        except APIKey.DoesNotExist:
            return Response({'error': 'Key not found'}, status=404)

    @action(detail=False, methods=['get'])
    def scopes(self, request):
        return Response({
            'scopes': [
                {'value': 'read',       'label': 'Read Only',         'description': 'GET requests only'},
                {'value': 'analytics',  'label': 'Analytics',         'description': 'Analytics endpoints'},
                {'value': 'postback',   'label': 'Postback Only',     'description': 'CPAlead postback only'},
                {'value': 'publisher',  'label': 'Publisher Tools',   'description': 'Offerwall, lockers, smartlinks'},
                {'value': 'write',      'label': 'Read + Write',      'description': 'All non-admin endpoints'},
                {'value': 'admin',      'label': 'Admin Full Access', 'description': 'All endpoints including admin'},
            ]
        })


# ─────────────────────────────────────────────
# Session ViewSet
# ─────────────────────────────────────────────

class SessionViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/sessions/            — List active sessions
    POST /api/cms/sessions/{id}/revoke/ — Revoke a session
    POST /api/cms/sessions/revoke_all/ — Revoke all other sessions
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [CMSWriteThrottle]

    @action(detail=False, methods=['get'])
    def active(self, request):
        from api.cms.models_new.sessions import UserSession
        from api.cms.helpers import get_client_ip
        sessions = UserSession.get_active_for_user(request.user)
        current_ip = get_client_ip(request)
        return Response({
            'results': [{
                'id': s.id,
                'ip_address': s.ip_address,
                'device_type': s.device_type,
                'country': s.country,
                'is_current': s.ip_address == current_ip,
                'last_activity': s.last_activity.isoformat(),
                'created_at': s.created_at.isoformat(),
            } for s in sessions],
            'count': sessions.count(),
        })

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        from api.cms.models_new.sessions import UserSession
        try:
            session = UserSession.objects.get(id=pk, user=request.user, is_active=True)
            session.revoke()
            return Response({'success': True})
        except UserSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)

    @action(detail=False, methods=['post'])
    def revoke_all(self, request):
        from api.cms.models_new.sessions import UserSession
        current_session = request.session.session_key if hasattr(request, 'session') else None
        UserSession.revoke_all_for_user(request.user, except_session=current_session)
        return Response({'success': True, 'message': 'All other sessions revoked'})


# ─────────────────────────────────────────────
# Landing Page ViewSet
# ─────────────────────────────────────────────

class LandingPageViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/landing-pages/            — List active landing pages
    GET  /api/cms/landing-pages/{slug}/     — Get single landing page
    GET  /api/cms/landing-pages/by_niche/   — Filter by gaming niche
    POST /api/cms/landing-pages/            — Create (admin)
    POST /api/cms/landing-pages/{id}/track/ — Track view/click
    """
    authentication_classes = [JWTAuthentication]
    pagination_class = CMSSmallPagination

    def get_permissions(self):
        if self.action in ('list_pages', 'by_slug', 'by_niche', 'track'):
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def list_pages(self, request):
        from api.cms.models_new.landing_pages import LandingPage
        niche = request.query_params.get('niche', '')
        qs = LandingPage.objects.filter(is_active=True)
        if niche:
            qs = qs.filter(niche=niche)
        qs = qs.order_by('-is_featured', '-conversions')[:50]
        return Response({
            'results': [{
                'id': p.id, 'name': p.name, 'slug': p.slug,
                'niche': p.niche, 'headline': p.headline,
                'cta_text': p.cta_text, 'thumbnail': p.thumbnail,
                'background_color': p.background_color,
                'accent_color': p.accent_color,
                'conversion_rate': p.conversion_rate,
                'is_featured': p.is_featured,
            } for p in qs],
            'count': qs.count(),
        })

    @action(detail=False, methods=['get'],
            url_path='by-slug/(?P<slug>[^/.]+)',
            permission_classes=[AllowAny])
    def by_slug(self, request, slug=None):
        from api.cms.models_new.landing_pages import LandingPage
        from django.db.models import F
        try:
            page = LandingPage.objects.get(slug=slug, is_active=True)
            LandingPage.objects.filter(pk=page.pk).update(views=F('views') + 1)
            return Response({
                'id': page.id, 'name': page.name, 'slug': page.slug,
                'niche': page.niche, 'headline': page.headline,
                'sub_headline': page.sub_headline,
                'description': page.description,
                'cta_text': page.cta_text, 'thumbnail': page.thumbnail,
                'background_color': page.background_color,
                'accent_color': page.accent_color,
                'custom_css': page.custom_css,
                'custom_html': page.custom_html,
                'locker_id': page.locker_id,
                'smartlink_id': page.smartlink_id,
            })
        except LandingPage.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def by_niche(self, request):
        from api.cms.models_new.landing_pages import LandingPage, GAMING_NICHES
        return Response({
            'niches': [{'value': k, 'label': v} for k, v in GAMING_NICHES],
            'counts': {
                niche: LandingPage.objects.filter(niche=niche, is_active=True).count()
                for niche, _ in GAMING_NICHES
            }
        })

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def track(self, request, pk=None):
        from api.cms.models_new.landing_pages import LandingPage
        from django.db.models import F
        event = request.data.get('event', 'view')
        try:
            if event == 'click':
                LandingPage.objects.filter(pk=pk).update(clicks=F('clicks') + 1)
            elif event == 'conversion':
                LandingPage.objects.filter(pk=pk).update(conversions=F('conversions') + 1)
            return Response({'tracked': event})
        except Exception:
            return Response({'error': 'Failed'}, status=400)


# ─────────────────────────────────────────────
# Fast Pay ViewSet
# ─────────────────────────────────────────────

class FastPayViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/fast-pay/eligible/    — Get eligible users (admin)
    GET  /api/cms/fast-pay/stats/       — Fast Pay statistics
    POST /api/cms/fast-pay/run/         — Trigger manual Fast Pay run (admin)
    GET  /api/cms/fast-pay/my_status/   — Check if I'm eligible
    """
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action == 'my_status':
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def eligible(self, request):
        from api.cms.fast_pay import FastPayService
        users = FastPayService.get_eligible_users()
        return Response({'eligible_users': users, 'count': len(users)})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.cms.fast_pay import FastPayService
        days = int(request.query_params.get('days', 30))
        return Response(FastPayService.get_fast_pay_stats(days))

    @action(detail=False, methods=['post'])
    def run(self, request):
        from api.cms.fast_pay import FastPayService
        # Remove cache lock to allow manual run
        from django.core.cache import cache
        from django.utils import timezone
        cache.delete(f"cms:fast_pay:{timezone.now().date()}")
        result = FastPayService.run_daily_fast_pay()
        return Response(result)

    @action(detail=False, methods=['get'])
    def my_status(self, request):
        from api.cms.fast_pay import FastPayService
        from api.cms.models_new.cpalead import UserVirtualBalance, VirtualCurrency
        from api.cms.models_new.withdrawal import PayoutMethod
        try:
            vc = VirtualCurrency.get_active()
            bal = UserVirtualBalance.objects.get(user=request.user)
            has_method = PayoutMethod.objects.filter(
                user=request.user, is_default=True, is_verified=True
            ).exists()
            if not vc:
                return Response({'eligible': False, 'reason': 'No currency configured'})
            min_coins = vc.usd_to_virtual(FastPayService.FAST_PAY_MIN_USD)
            eligible = bal.balance >= min_coins and has_method
            return Response({
                'eligible': eligible,
                'balance_coins': float(bal.balance),
                'min_coins_required': float(min_coins),
                'has_payout_method': has_method,
                'reason': '' if eligible else 'Insufficient balance or no verified payout method',
            })
        except Exception as e:
            return Response({'eligible': False, 'reason': str(e)})


# ─────────────────────────────────────────────
# Currency ViewSet
# ─────────────────────────────────────────────

class CurrencyViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET /api/cms/currency/rates/          — Current exchange rates
    GET /api/cms/currency/supported/      — Supported currencies
    GET /api/cms/currency/convert/        — Convert USD to currency
    GET /api/cms/currency/my_currency/    — Get user's currency
    POST /api/cms/currency/set/           — Set preferred currency
    """
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action in ('rates', 'supported', 'convert'):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def rates(self, request):
        from api.cms.currency import CurrencyService
        rates = CurrencyService.get_rates()
        return Response({'rates': rates, 'base': 'USD'})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def supported(self, request):
        from api.cms.currency import CurrencyService
        return Response({'currencies': CurrencyService.get_supported_currencies()})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def convert(self, request):
        from api.cms.currency import CurrencyService
        from decimal import Decimal
        try:
            usd = Decimal(str(request.query_params.get('usd', '1')))
            to = request.query_params.get('to', 'USD').upper()
            amount = CurrencyService.convert(usd, to)
            formatted = CurrencyService.format(usd, to)
            return Response({
                'usd': float(usd),
                'currency': to,
                'amount': float(amount),
                'formatted': formatted,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def my_currency(self, request):
        from api.cms.currency import CurrencyService
        currency = CurrencyService.get_user_currency(request.user)
        return Response({'currency': currency})

    @action(detail=False, methods=['post'])
    def set_currency(self, request):
        from api.cms.currency import FALLBACK_RATES
        from api.cms.models_new.withdrawal import UserProfile
        currency = request.data.get('currency', 'USD').upper()
        if currency not in FALLBACK_RATES:
            return Response({'error': f'Unsupported currency: {currency}'}, status=400)
        UserProfile.objects.filter(user=request.user).update(preferred_currency=currency)
        return Response({'success': True, 'currency': currency})


# ─────────────────────────────────────────────
# MCP ViewSet (AI Agent Control)
# ─────────────────────────────────────────────

class MCPViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/mcp/tools/         — List available MCP tools
    POST /api/cms/mcp/execute/       — Execute an MCP tool
    GET  /api/cms/mcp/resources/     — List MCP resources
    GET  /api/cms/mcp/status/        — MCP server status
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def tools(self, request):
        from api.cms.mcp_server import CMS_MCP_TOOLS
        return Response({'tools': CMS_MCP_TOOLS, 'count': len(CMS_MCP_TOOLS)})

    @action(detail=False, methods=['post'])
    def execute(self, request):
        from api.cms.mcp_server import CMSMCPToolExecutor
        tool_name = request.data.get('tool', '')
        arguments = request.data.get('arguments', {})
        if not tool_name:
            return Response({'error': 'tool name required'}, status=400)
        result = CMSMCPToolExecutor.execute(tool_name, arguments)
        return Response({'result': result, 'tool': tool_name})

    @action(detail=False, methods=['get'])
    def resources(self, request):
        from api.cms.mcp_server import CMSMCPServer
        resources = CMSMCPServer._get_resources()
        return Response({'resources': resources})

    @action(detail=False, methods=['get'])
    def server_status(self, request):
        from api.cms.mcp_server import CMSMCPServer
        return Response({
            'server': CMSMCPServer.SERVER_INFO,
            'tools_count': 15,
            'status': 'running',
            'protocol_version': '2024-11-05',
        })


# ─────────────────────────────────────────────
# Comment ViewSet (PUBLIC)
# ─────────────────────────────────────────────

class CommentViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/comments/              — List comments for content
    POST /api/cms/comments/              — Post a comment
    POST /api/cms/comments/{id}/reply/   — Reply to comment
    POST /api/cms/comments/{id}/react/   — Like/dislike comment
    DELETE /api/cms/comments/{id}/       — Delete own comment
    """
    authentication_classes = [JWTAuthentication]
    pagination_class = CMSSmallPagination

    def get_permissions(self):
        if self.action in ('list_comments',):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def list_comments(self, request):
        from api.cms.models_new.comments import Comment
        content_type = request.query_params.get('type', 'blog_post')
        object_id = request.query_params.get('id')
        if not object_id:
            return Response({'error': 'id required'}, status=400)
        comments = Comment.objects.filter(
            content_type=content_type,
            object_id=int(object_id),
            status='approved',
            parent=None,
        ).select_related('user').order_by('-is_pinned', 'created_at')[:50]

        return Response({
            'results': [{
                'id': c.id,
                'author': c.author_display,
                'body': c.body,
                'likes': c.likes,
                'dislikes': c.dislikes,
                'is_pinned': c.is_pinned,
                'reply_count': c.replies.filter(status='approved').count(),
                'created_at': c.created_at.isoformat(),
            } for c in comments],
            'count': comments.count(),
        })

    @action(detail=False, methods=['post'])
    def add_comment(self, request):
        from api.cms.models_new.comments import Comment
        from api.cms.ai_moderation import CommentModerationService
        from api.cms.helpers import get_client_ip
        body = request.data.get('body', '').strip()
        content_type = request.data.get('content_type', 'blog_post')
        object_id = request.data.get('object_id')
        if not body or not object_id:
            return Response({'error': 'body and object_id required'}, status=400)
        if len(body) > 2000:
            return Response({'error': 'Comment too long (max 2000 chars)'}, status=400)

        # Moderation check
        ip = get_client_ip(request)
        action_status, reason = CommentModerationService.check_comment(
            body, request.user, ip
        )
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=int(object_id),
            user=request.user,
            body=body,
            status=action_status,
            ip_address=ip or None,
        )
        return Response({
            'id': comment.id,
            'status': comment.status,
            'message': 'Comment posted!' if action_status == 'approved' else 'Comment pending review.',
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        from api.cms.models_new.comments import Comment
        from api.cms.ai_moderation import CommentModerationService
        from api.cms.helpers import get_client_ip
        try:
            parent = Comment.objects.get(id=pk, status='approved')
        except Comment.DoesNotExist:
            return Response({'error': 'Comment not found'}, status=404)
        body = request.data.get('body', '').strip()
        if not body:
            return Response({'error': 'body required'}, status=400)
        ip = get_client_ip(request)
        action_status, _ = CommentModerationService.check_comment(body, request.user, ip)
        reply = Comment.objects.create(
            content_type=parent.content_type,
            object_id=parent.object_id,
            user=request.user,
            parent=parent,
            depth=parent.depth + 1,
            body=body,
            status=action_status,
            ip_address=ip or None,
        )
        return Response({'id': reply.id, 'status': reply.status}, status=201)

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        from api.cms.models_new.comments import Comment, CommentReaction
        from django.db.models import F
        try:
            comment = Comment.objects.get(id=pk, status='approved')
        except Comment.DoesNotExist:
            return Response({'error': 'Comment not found'}, status=404)
        reaction_type = request.data.get('reaction', 'like')
        if reaction_type not in ('like', 'dislike'):
            return Response({'error': 'reaction must be like or dislike'}, status=400)
        # Toggle or update reaction
        existing = CommentReaction.objects.filter(comment=comment, user=request.user).first()
        if existing:
            if existing.reaction == reaction_type:
                # Remove reaction
                if reaction_type == 'like':
                    Comment.objects.filter(pk=pk).update(likes=F('likes') - 1)
                else:
                    Comment.objects.filter(pk=pk).update(dislikes=F('dislikes') - 1)
                existing.delete()
                return Response({'action': 'removed', 'reaction': reaction_type})
            else:
                # Change reaction
                existing.reaction = reaction_type
                existing.save()
        else:
            CommentReaction.objects.create(
                comment=comment, user=request.user, reaction=reaction_type
            )
        if reaction_type == 'like':
            Comment.objects.filter(pk=pk).update(likes=F('likes') + 1)
        else:
            Comment.objects.filter(pk=pk).update(dislikes=F('dislikes') + 1)
        comment.refresh_from_db()
        return Response({
            'action': 'added',
            'reaction': reaction_type,
            'likes': comment.likes,
            'dislikes': comment.dislikes,
        })

    @action(detail=True, methods=['delete'])
    def delete_comment(self, request, pk=None):
        from api.cms.models_new.comments import Comment
        try:
            comment = Comment.objects.get(id=pk)
        except Comment.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        if comment.user != request.user and not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        comment.status = 'rejected'
        comment.save(update_fields=['status'])
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)
