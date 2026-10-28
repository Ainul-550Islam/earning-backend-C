"""
SmartLink Click Replay & Attribution Dispute ViewSet
Allows publishers to replay missed conversions and raise attribution disputes.

Endpoints:
  POST /api/smartlink/attribution/replay/
       Re-attempt conversion attribution for a specific click + postback.
       Used when original postback failed or was delayed.

  POST /api/smartlink/attribution/dispute/
       Raise a dispute for a conversion that was scrubbed or incorrectly attributed.

  GET  /api/smartlink/attribution/dispute/
       List publisher's open disputes.

  POST /api/smartlink/attribution/dispute/{id}/resolve/
       Admin: resolve a dispute (approve or reject adjustment).

  GET  /api/smartlink/attribution/window/
       Return the current attribution window config for the publisher's tier.
"""
import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

User = get_user_model()
logger = logging.getLogger('smartlink.viewsets.attribution')


# ─────────────────────────────────────────────────────────────────────────────
# Inline serializers
# ─────────────────────────────────────────────────────────────────────────────

class ReplaySerializer(serializers.Serializer):
    """Input for manual conversion replay."""
    click_id       = serializers.IntegerField(
        help_text='Click PK to re-attribute.'
    )
    offer_id       = serializers.IntegerField(
        help_text='Offer ID the conversion belongs to.'
    )
    payout         = serializers.FloatField(
        min_value=0,
        help_text='Payout amount in USD.'
    )
    transaction_id = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default='',
        help_text='Advertiser transaction reference for dedup.',
    )
    reason         = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default='',
        help_text='Reason for replay (e.g. delayed postback, network error).',
    )


class DisputeCreateSerializer(serializers.Serializer):
    """Input for raising an attribution dispute."""
    TYPE_CHOICES = [
        ('scrub_dispute',       'Conversion was incorrectly scrubbed'),
        ('attribution_dispute', 'Conversion attributed to wrong click'),
        ('missing_conversion',  'Conversion postback was not received'),
        ('payout_dispute',      'Payout amount is incorrect'),
    ]
    click_id    = serializers.IntegerField(help_text='Click PK under dispute.')
    offer_id    = serializers.IntegerField(help_text='Offer ID involved.')
    dispute_type = serializers.ChoiceField(choices=TYPE_CHOICES)
    description  = serializers.CharField(
        max_length=2000,
        help_text='Detailed description of the issue.',
    )
    expected_payout = serializers.FloatField(
        min_value=0, required=False, allow_null=True, default=None,
        help_text='What the publisher believes the payout should be.',
    )
    evidence_url = serializers.URLField(
        required=False, allow_blank=True, default='',
        help_text='Link to screenshot, CSV, or other evidence.',
    )


class DisputeResolveSerializer(serializers.Serializer):
    """Admin input for resolving a dispute."""
    DECISION_CHOICES = [
        ('approved', 'Dispute approved — adjust payout'),
        ('rejected', 'Dispute rejected — no adjustment'),
        ('partial',  'Partial adjustment agreed'),
    ]
    decision       = serializers.ChoiceField(choices=DECISION_CHOICES)
    adjusted_payout = serializers.FloatField(
        min_value=0, required=False, allow_null=True, default=None,
    )
    admin_note     = serializers.CharField(max_length=1000, required=False, allow_blank=True)


# ─────────────────────────────────────────────────────────────────────────────
# AttributionViewSet
# ─────────────────────────────────────────────────────────────────────────────

class AttributionViewSet(viewsets.ViewSet):
    """
    Click replay and attribution dispute management.
    """
    permission_classes = [IsAuthenticated]

    # ── Replay ─────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='replay')
    def replay(self, request):
        """
        POST /api/smartlink/attribution/replay/
        Re-run attribution for a specific click. Useful when the original
        postback arrived late or was dropped due to a network error.

        Only the publisher who owns the SmartLink can replay its clicks.
        Admins can replay any click.
        """
        serializer = ReplaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from api.smartlink.models import Click
        from django.shortcuts import get_object_or_404

        if request.user.is_staff:
            click = get_object_or_404(Click, pk=data['click_id'])
        else:
            click = get_object_or_404(
                Click, pk=data['click_id'],
                smartlink__publisher=request.user
            )

        if click.is_converted:
            return Response(
                {
                    'detail': (
                        f"Click #{click.pk} is already attributed "
                        f"(payout=${click.payout}). "
                        f"If this is wrong, raise a dispute instead."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        from ..services.click.ClickAttributionService import ClickAttributionService
        svc = ClickAttributionService()

        # Override window to allow replays from up to 30 days ago
        svc.window_hours = 30 * 24

        result_click = svc.attribute(
            offer_id=data['offer_id'],
            sub1=str(click.pk),  # use click PK as definitive sub1
            ip=click.ip,
            payout=data['payout'],
            transaction_id=data.get('transaction_id', ''),
        )

        if result_click:
            logger.info(
                f"Click replay successful: click#{click.pk} "
                f"offer#{data['offer_id']} payout={data['payout']} "
                f"by {request.user.username} reason={data.get('reason','')}"
            )
            return Response({
                'success': True,
                'click_id': click.pk,
                'offer_id': data['offer_id'],
                'payout':   data['payout'],
                'attributed_at': timezone.now(),
                'message': f"Conversion replayed successfully for click #{click.pk}.",
            })
        else:
            return Response(
                {
                    'success': False,
                    'detail': (
                        f"Attribution failed for click #{click.pk}. "
                        f"The click may belong to a different offer, or the "
                        f"30-day replay window has passed."
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    # ── Dispute ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get', 'post'], url_path='dispute')
    def dispute(self, request):
        """
        GET  /api/smartlink/attribution/dispute/ — list open disputes
        POST /api/smartlink/attribution/dispute/ — raise new dispute
        """
        if request.method == 'GET':
            return self._list_disputes(request)
        return self._create_dispute(request)

    def _list_disputes(self, request):
        """Return publisher's attribution disputes (most recent first)."""
        from django.core.cache import cache
        cache_key = f'disputes:{request.user.pk}'
        disputes = cache.get(cache_key, [])
        if request.user.is_staff:
            # Admin sees all disputes
            disputes = cache.get('disputes:all', [])
        return Response({
            'count': len(disputes),
            'results': disputes,
        })

    def _create_dispute(self, request):
        """Raise a new attribution dispute."""
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Verify the click belongs to the publisher
        from api.smartlink.models import Click
        from django.shortcuts import get_object_or_404
        if request.user.is_staff:
            click = get_object_or_404(Click, pk=data['click_id'])
        else:
            click = get_object_or_404(
                Click, pk=data['click_id'],
                smartlink__publisher=request.user,
            )

        import uuid
        dispute_id = str(uuid.uuid4())[:8].upper()
        dispute = {
            'id':               dispute_id,
            'publisher_id':     request.user.pk,
            'publisher':        request.user.username,
            'click_id':         click.pk,
            'offer_id':         data['offer_id'],
            'dispute_type':     data['dispute_type'],
            'description':      data['description'],
            'expected_payout':  data.get('expected_payout'),
            'evidence_url':     data.get('evidence_url', ''),
            'status':           'open',
            'created_at':       timezone.now().isoformat(),
            'resolved_at':      None,
            'decision':         None,
            'adjusted_payout':  None,
            'admin_note':       '',
        }

        # Persist to cache (in production, use a Django model instead)
        from django.core.cache import cache
        publisher_key = f'disputes:{request.user.pk}'
        all_key       = 'disputes:all'
        publisher_disputes = cache.get(publisher_key, [])
        all_disputes       = cache.get(all_key, [])
        publisher_disputes.insert(0, dispute)
        all_disputes.insert(0, dispute)
        cache.set(publisher_key, publisher_disputes[:100], 86400 * 30)
        cache.set(all_key,       all_disputes[:500],       86400 * 30)
        cache.set(f'dispute:{dispute_id}', dispute, 86400 * 30)

        # Notify admin
        try:
            from api.smartlink.services.notification.NotificationService import NotificationService
            admin = User.objects.filter(is_staff=True).first()
            if admin:
                NotificationService()._send_email(
                    user=admin,
                    subject=f'Attribution Dispute #{dispute_id} — {request.user.username}',
                    message=(
                        f"Publisher {request.user.username} raised a dispute:\n"
                        f"Type: {data['dispute_type']}\n"
                        f"Click: #{click.pk}\n"
                        f"Description: {data['description']}\n"
                        f"Review: /api/smartlink/attribution/dispute/"
                    ),
                )
        except Exception as e:
            logger.warning(f"Dispute admin notification failed: {e}")

        logger.info(
            f"Dispute #{dispute_id} raised by {request.user.username}: "
            f"click#{click.pk} type={data['dispute_type']}"
        )
        return Response({
            'dispute_id': dispute_id,
            'status': 'open',
            'message': (
                f"Dispute #{dispute_id} submitted. "
                f"Our team will review within 2 business days."
            ),
            'dispute': dispute,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'],
            url_path=r'dispute/(?P<dispute_id>[^/.]+)/resolve',
            permission_classes=[IsAuthenticated])
    def resolve_dispute(self, request, dispute_id=None):
        """
        POST /api/smartlink/attribution/dispute/{id}/resolve/
        Admin: approve or reject a dispute and optionally adjust payout.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DisputeResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from django.core.cache import cache
        dispute = cache.get(f'dispute:{dispute_id}')
        if not dispute:
            return Response({'detail': f'Dispute #{dispute_id} not found.'}, status=404)

        dispute.update({
            'status':          data['decision'],
            'resolved_at':     timezone.now().isoformat(),
            'decision':        data['decision'],
            'adjusted_payout': data.get('adjusted_payout'),
            'admin_note':      data.get('admin_note', ''),
            'resolved_by':     request.user.username,
        })
        cache.set(f'dispute:{dispute_id}', dispute, 86400 * 30)

        # If approved and adjustment needed, replay the attribution
        if data['decision'] in ('approved', 'partial') and data.get('adjusted_payout'):
            try:
                from api.smartlink.models import Click
                click = Click.objects.get(pk=dispute['click_id'])
                if not click.is_converted:
                    from ..services.click.ClickAttributionService import ClickAttributionService
                    svc = ClickAttributionService()
                    svc.window_hours = 90 * 24
                    svc.attribute(
                        offer_id=dispute['offer_id'],
                        sub1=str(click.pk),
                        ip=click.ip,
                        payout=data['adjusted_payout'],
                        transaction_id=f"DISPUTE-{dispute_id}",
                    )
            except Exception as e:
                logger.error(f"Dispute #{dispute_id} payout adjustment failed: {e}")

        # Notify publisher
        try:
            publisher = User.objects.get(pk=dispute['publisher_id'])
            from api.smartlink.services.notification.NotificationService import NotificationService
            NotificationService()._send_email(
                user=publisher,
                subject=f'Attribution Dispute #{dispute_id} — {data["decision"].title()}',
                message=(
                    f"Your dispute #{dispute_id} has been {data['decision']}.\n"
                    + (f"Adjusted payout: ${data['adjusted_payout']}\n"
                       if data.get('adjusted_payout') else '')
                    + (f"Admin note: {data['admin_note']}\n"
                       if data.get('admin_note') else '')
                ),
            )
        except Exception as e:
            logger.warning(f"Dispute resolution notification failed: {e}")

        logger.info(
            f"Dispute #{dispute_id} resolved: {data['decision']} "
            f"by {request.user.username}"
        )
        return Response({
            'dispute_id': dispute_id,
            'status':     data['decision'],
            'message':    f'Dispute #{dispute_id} {data["decision"]}.',
            'dispute':    dispute,
        })

    # ── Attribution Window Info ─────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='window')
    def window(self, request):
        """
        GET /api/smartlink/attribution/window/

        Return the effective attribution window for the requesting publisher.

        Resolution order:
          1. Per-publisher override (PublisherProfile.attribution_window_days)
          2. Global setting (settings.SMARTLINK_ATTRIBUTION_WINDOW_HOURS)
          3. Hard default: 24 hours

        Admin response also includes the global setting for comparison.
        """
        from django.conf import settings as dj_settings
        global_hours = getattr(dj_settings, 'SMARTLINK_ATTRIBUTION_WINDOW_HOURS', 24)

        # Check per-publisher override
        per_publisher_days  = None
        effective_hours     = global_hours
        publisher_override  = False

        try:
            from api.smartlink.models.billing import PublisherProfile
            profile = PublisherProfile.objects.filter(
                publisher=request.user
            ).only('attribution_window_days').first()
            if profile and profile.attribution_window_days is not None:
                per_publisher_days = profile.attribution_window_days
                effective_hours    = per_publisher_days * 24
                publisher_override = True
        except Exception:
            pass  # Fail-open — use global setting

        response_data = {
            'attribution_window_hours':  effective_hours,
            'attribution_window_days':   round(effective_hours / 24, 1),
            'publisher_override_active': publisher_override,
            'replay_window_days':        30,
            'model':                     'last_click',
            'note': (
                f'Conversions received within {effective_hours}h of a click '
                f'are automatically attributed. '
                + (
                    f'Your account has a custom {per_publisher_days}-day window set. '
                    if publisher_override
                    else
                    f'Set SMARTLINK_ATTRIBUTION_WINDOW_HOURS in Django settings '
                    f'or configure a per-publisher override via your profile to change.'
                )
            ),
        }

        # Admin sees global setting alongside effective window
        if request.user.is_staff:
            response_data['global_window_hours'] = global_hours
            response_data['global_window_days']  = round(global_hours / 24, 1)

        return Response(response_data)
