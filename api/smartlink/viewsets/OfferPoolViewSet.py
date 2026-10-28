import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from api.smartlink.models import OfferPool, OfferPoolEntry
from api.smartlink.serializers.OfferPoolSerializer import OfferPoolSerializer
from api.smartlink.serializers.OfferPoolEntrySerializer import OfferPoolEntrySerializer
from api.smartlink.permissions import IsPublisher, IsSmartLinkOwner
from ..services.rotation.CapTrackerService import CapTrackerService

logger = logging.getLogger('smartlink.viewsets.offer_pool')


class OfferPoolViewSet(viewsets.ModelViewSet):
    """Manage the offer pool for a SmartLink."""
    serializer_class = OfferPoolSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return OfferPool.objects.filter(smartlink_id=sl_pk)

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        serializer.save(smartlink_id=sl_pk)

    @action(detail=True, methods=['get'], url_path='cap-usage')
    def cap_usage(self, request, smartlink_pk=None, pk=None):
        """GET cap usage for all entries in this pool."""
        pool = self.get_object()
        cap_service = CapTrackerService()
        usage = [cap_service.get_usage(e) for e in pool.get_active_entries()]
        return Response(usage)

    @action(detail=True, methods=['post'], url_path='sync-from-catalog')
    def sync_from_catalog(self, request, smartlink_pk=None, pk=None):
        """
        POST /api/smartlink/smartlinks/{smartlink_pk}/pool/{id}/sync-from-catalog/

        Sync this SmartLink's offer pool from the offer_inventory catalog.

        Reads offer IDs from the request body and adds any missing ones as
        OfferPoolEntry rows. Existing entries are left untouched (their weights,
        priorities and caps are preserved). Offers that are not in the submitted
        list but already in the pool are optionally deactivated (not deleted),
        so historical data is kept.

        Request body (JSON):
        {
            "offer_ids": [1, 2, 3],          // required: offer PKs from offer_inventory
            "default_weight": 100,           // optional, default 100
            "default_priority": 0,           // optional, default 0
            "deactivate_missing": false      // optional, default false
                                             // when true: deactivate pool entries whose
                                             // offer_id is NOT in offer_ids
        }

        Response (200 OK / 207 Multi-Status when some offers had errors):
        {
            "added": [{"offer_id": 3, "pool_entry_id": 42}],
            "already_present": [1, 2],
            "deactivated": [],
            "errors": [],
            "pool_id": 7,
            "smartlink_pk": "my-smartlink"
        }

        Access rules:
          - Publisher must have can_edit_pool=True on their PublisherSmartLink
            assignment, OR be staff.
        """
        pool = self.get_object()

        # ── Permission check ─────────────────────────────────────────────────
        if not request.user.is_staff:
            from api.smartlink.models.publisher import PublisherSmartLink
            assignment = PublisherSmartLink.objects.filter(
                publisher=request.user,
                smartlink_id=smartlink_pk,
                is_active=True,
                can_edit_pool=True,
            ).first()
            if not assignment:
                return Response(
                    {
                        'detail': (
                            'You do not have permission to edit this pool. '
                            'can_edit_pool must be True on your SmartLink assignment.'
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # ── Validate input ───────────────────────────────────────────────────
        offer_ids = request.data.get('offer_ids')
        if not isinstance(offer_ids, list) or not offer_ids:
            return Response(
                {'detail': 'offer_ids must be a non-empty list of offer PKs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            offer_ids = [int(oid) for oid in offer_ids]
        except (TypeError, ValueError):
            return Response(
                {'detail': 'All values in offer_ids must be integers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        default_weight     = int(request.data.get('default_weight',   100))
        default_priority   = int(request.data.get('default_priority', 0))
        deactivate_missing = bool(request.data.get('deactivate_missing', False))

        # ── Resolve Offer model ──────────────────────────────────────────────
        from django.apps import apps
        from django.conf import settings as dj_settings
        offer_model_label = getattr(
            dj_settings, 'SMARTLINK_OFFER_MODEL', 'offer_inventory.Offer'
        )
        try:
            OfferModel = apps.get_model(offer_model_label)
        except LookupError:
            return Response(
                {
                    'detail': (
                        f'Offer model "{offer_model_label}" not found. '
                        'Check SMARTLINK_OFFER_MODEL in settings.'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # ── Sync logic ───────────────────────────────────────────────────────
        existing_entries = {
            e.offer_id: e
            for e in OfferPoolEntry.objects.filter(pool=pool)
        }

        added           = []
        already_present = []
        deactivated     = []
        errors          = []

        # 1. Add / re-activate submitted offers
        for offer_id in offer_ids:
            if offer_id in existing_entries:
                entry = existing_entries[offer_id]
                if not entry.is_active:
                    # Re-activate previously deactivated entry
                    entry.is_active = True
                    entry.save(update_fields=['is_active', 'updated_at'])
                    added.append({
                        'offer_id':      offer_id,
                        'pool_entry_id': entry.pk,
                        'note':          're-activated',
                    })
                else:
                    already_present.append(offer_id)
                continue

            # Verify offer exists in catalog
            try:
                offer = OfferModel.objects.get(pk=offer_id)
            except OfferModel.DoesNotExist:
                errors.append({
                    'offer_id': offer_id,
                    'error':    f'Offer #{offer_id} not found in {offer_model_label}.',
                })
                logger.warning(
                    f"sync-from-catalog: offer#{offer_id} not found in catalog "
                    f"(pool={pool.pk} smartlink={smartlink_pk})"
                )
                continue

            try:
                entry = OfferPoolEntry.objects.create(
                    pool=pool,
                    offer=offer,
                    weight=default_weight,
                    priority=default_priority,
                    is_active=True,
                )
                added.append({'offer_id': offer_id, 'pool_entry_id': entry.pk})
                logger.info(
                    f"sync-from-catalog: added offer#{offer_id} → entry#{entry.pk} "
                    f"pool={pool.pk} smartlink={smartlink_pk}"
                )
            except Exception as exc:
                errors.append({'offer_id': offer_id, 'error': str(exc)})
                logger.error(
                    f"sync-from-catalog: failed to create entry for offer#{offer_id}: {exc}"
                )

        # 2. Optionally deactivate offers not in the submitted list
        if deactivate_missing:
            submitted_set = set(offer_ids)
            for offer_id, entry in existing_entries.items():
                if offer_id not in submitted_set and entry.is_active:
                    entry.is_active = False
                    entry.save(update_fields=['is_active', 'updated_at'])
                    deactivated.append({
                        'offer_id':      offer_id,
                        'pool_entry_id': entry.pk,
                    })
                    logger.info(
                        f"sync-from-catalog: deactivated offer#{offer_id} "
                        f"entry#{entry.pk} pool={pool.pk}"
                    )

        http_status = (
            status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        )
        return Response(
            {
                'added':           added,
                'already_present': already_present,
                'deactivated':     deactivated,
                'errors':          errors,
                'pool_id':         pool.pk,
                'smartlink_pk':    smartlink_pk,
            },
            status=http_status,
        )


class OfferPoolEntryViewSet(viewsets.ModelViewSet):
    """Manage individual offer entries within a pool."""
    serializer_class = OfferPoolEntrySerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return OfferPoolEntry.objects.filter(pool__smartlink_id=sl_pk).select_related('offer')

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        pool = OfferPool.objects.get(smartlink_id=sl_pk)
        serializer.save(pool=pool)

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, smartlink_pk=None, pk=None):
        entry = self.get_object()
        entry.is_active = not entry.is_active
        entry.save(update_fields=['is_active', 'updated_at'])
        return Response({'is_active': entry.is_active})
