"""
SmartLink ViewSet Mixins
=========================
Extracts the repeated patterns that appeared in 10–12 viewsets before this file:

  • SmartLinkScopedMixin  — repeated get_queryset(sl_pk) + is_staff guard
  • PublisherScopedMixin  — repeated publisher=request.user filter
  • ReadOnlyAdminMixin    — 12 viewsets: if not is_staff → 403 for write ops
  • IPExtractMixin        — moved from middleware.py + postback/views.py

Before this file every viewset had inline copies of:
    sl_pk = self.kwargs.get('smartlink_pk')
    qs = SomeModel.objects.filter(smartlink_id=sl_pk)
    if not self.request.user.is_staff:
        qs = qs.filter(smartlink__publisher=self.request.user)
    return qs

Now they inherit SmartLinkScopedMixin and supply only:
    model_class = ClickSession
    select_related_fields = ('smartlink', 'offer')
"""
import logging
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger("smartlink.viewsets.mixins")


# ─────────────────────────────────────────────────────────────────────────────
# 1. SmartLinkScopedMixin
#    Used by: ClickViewSet, ClickSessionViewSet, BotClickViewSet,
#             ABTestViewSet, GeoTargetingViewSet, DeviceTargetingViewSet,
#             OSTargetingViewSet, OfferPoolViewSet, SmartLinkStatViewSet,
#             TargetingRuleViewSet, RedirectChainViewSet, OfferPoolEntryViewSet
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkScopedMixin:
    """
    Scoped queryset for models that have a FK to SmartLink.

    Subclass requirements:
        model_class             — the Django model to query
        sl_fk_field             — FK field name to SmartLink (default 'smartlink')
        publisher_path          — ORM path to publisher from the model (default 'smartlink__publisher')
        select_related_fields   — tuple of select_related paths (default ())
        prefetch_related_fields — tuple of prefetch_related paths (default ())
        extra_filters           — dict of extra filter kwargs always applied (default {})

    The mixin builds:
        qs = model_class.objects.filter(**{f"{sl_fk_field}_id": sl_pk})
        if not is_staff:
            qs = qs.filter(**{publisher_path: request.user})
    """
    model_class             = None
    sl_fk_field             = "smartlink"
    publisher_path          = "smartlink__publisher"
    select_related_fields   = ()
    prefetch_related_fields = ()
    extra_filters           = {}

    def get_queryset(self):
        sl_pk = self.kwargs.get("smartlink_pk")
        user  = self.request.user

        if self.model_class is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must set model_class"
            )

        qs = self.model_class.objects.filter(
            **{f"{self.sl_fk_field}_id": sl_pk},
            **self.extra_filters,
        )
        if not user.is_staff:
            qs = qs.filter(**{self.publisher_path: user})

        if self.select_related_fields:
            qs = qs.select_related(*self.select_related_fields)
        if self.prefetch_related_fields:
            qs = qs.prefetch_related(*self.prefetch_related_fields)

        return qs

    def perform_create(self, serializer):
        """Default perform_create: inject smartlink_id from URL."""
        serializer.save(**{f"{self.sl_fk_field}_id": self.kwargs.get("smartlink_pk")})


# ─────────────────────────────────────────────────────────────────────────────
# 2. PublisherScopedMixin
#    Used by: SmartLinkViewSet, v2/SmartLinkV2ViewSet,
#             PublisherAPIViewSet, PublisherProfileViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PublisherScopedMixin:
    """
    Scoped queryset for models whose root FK is the publisher (User).

    Subclass requirements:
        model_class           — the Django model to query
        publisher_field       — FK field name to User (default 'publisher')
        is_archived_field     — optional boolean field to filter out archived rows
        select_related_fields — tuple of select_related paths (default ())

    Builds:
        qs = model_class.objects.filter(publisher=user)
        if is_archived_field:
            qs = qs.filter(**{f"{is_archived_field}": False})
    """
    model_class           = None
    publisher_field       = "publisher"
    is_archived_field     = None
    select_related_fields = ()

    def get_queryset(self):
        user = self.request.user

        if self.model_class is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must set model_class"
            )

        qs = self.model_class.objects.all() if user.is_staff else \
             self.model_class.objects.filter(**{self.publisher_field: user})

        if self.is_archived_field:
            qs = qs.filter(**{self.is_archived_field: False})

        if self.select_related_fields:
            qs = qs.select_related(*self.select_related_fields)

        return qs


# ─────────────────────────────────────────────────────────────────────────────
# 3. AdminWriteMixin
#    Used by: PublisherAllowListViewSet, PublisherBlockListViewSet,
#             FloatingModelViewSets (toggle actions), UtilityViewSet
# ─────────────────────────────────────────────────────────────────────────────

class AdminWriteMixin:
    """
    Restrict create/update/delete to staff only; read is unrestricted.

    Previously every viewset with admin-only writes had inline blocks:
        if not request.user.is_staff:
            return Response({'detail': '...'}, status=403)

    Now simply inherit this mixin alongside ModelViewSet.
    The mixin gates create(), update(), partial_update(), and destroy().
    retrieve() and list() are always allowed (subject to normal permissions).
    """
    _admin_only_message = "Only admin can perform this action."

    def _require_admin(self, request):
        """Return a 403 Response if the user is not staff, else None."""
        if not request.user.is_staff:
            return Response(
                {"detail": self._admin_only_message},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def create(self, request, *args, **kwargs):
        guard = self._require_admin(request)
        if guard:
            return guard
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        guard = self._require_admin(request)
        if guard:
            return guard
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        guard = self._require_admin(request)
        if guard:
            return guard
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        guard = self._require_admin(request)
        if guard:
            return guard
        return super().destroy(request, *args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# 4. PoolScopedMixin
#    Used by: OfferPoolViewSet, OfferPoolEntryViewSet
#    Before: both had identical perform_create logic
# ─────────────────────────────────────────────────────────────────────────────

class PoolScopedMixin:
    """
    Repeated in both OfferPoolViewSet and OfferPoolEntryViewSet:
        def perform_create(self, serializer):
            sl_pk = self.kwargs.get('smartlink_pk')
            pool = OfferPool.objects.get(smartlink_id=sl_pk)
            serializer.save(pool=pool)

    Now a single implementation.
    """
    def get_pool(self):
        from api.smartlink.models import OfferPool
        sl_pk = self.kwargs.get("smartlink_pk")
        return OfferPool.objects.get(smartlink_id=sl_pk)

    def perform_create(self, serializer):
        serializer.save(pool=self.get_pool())


# ─────────────────────────────────────────────────────────────────────────────
# 5. IPExtractMixin  (was duplicated in middleware.py AND postback/views.py)
#    Canonical location: api.smartlink.utils.get_client_ip()
#    This mixin provides a convenience method for class-based views.
# ─────────────────────────────────────────────────────────────────────────────

class IPExtractMixin:
    """
    Provides get_client_ip(request) for class-based views.
    The underlying logic now lives in api.smartlink.utils.get_client_ip()
    and is imported here — single implementation, used everywhere.
    """
    def get_client_ip(self, request) -> str:
        from api.smartlink.utils import get_client_ip
        return get_client_ip(request)
