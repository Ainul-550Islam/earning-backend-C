import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class NetworkPostbackConfigQuerySet(models.QuerySet):
    def active(self):
        from .choices import ValidatorStatus
        return self.filter(status=ValidatorStatus.ACTIVE)

    def by_network_key(self, key: str):
        return self.filter(network_key=key)

    def with_validators(self):
        return self.prefetch_related("lead_validators")


class PostbackLogQuerySet(models.QuerySet):
    def received(self):
        from .choices import PostbackStatus
        return self.filter(status=PostbackStatus.RECEIVED)

    def rewarded(self):
        from .choices import PostbackStatus
        return self.filter(status=PostbackStatus.REWARDED)

    def rejected(self):
        from .choices import PostbackStatus
        return self.filter(status=PostbackStatus.REJECTED)

    def failed(self):
        from .choices import PostbackStatus
        return self.filter(status=PostbackStatus.FAILED)

    def duplicates(self):
        from .choices import PostbackStatus
        return self.filter(status=PostbackStatus.DUPLICATE)

    def retryable(self):
        from .choices import PostbackStatus
        from .constants import MAX_POSTBACK_PROCESSING_RETRIES
        return self.filter(
            status=PostbackStatus.FAILED,
            retry_count__lt=MAX_POSTBACK_PROCESSING_RETRIES,
            next_retry_at__lte=timezone.now(),
        )

    def for_network(self, network):
        return self.filter(network=network)

    def for_lead(self, lead_id: str, network=None):
        qs = self.filter(lead_id=lead_id)
        if network:
            qs = qs.filter(network=network)
        return qs

    def in_date_range(self, start, end):
        return self.filter(received_at__range=[start, end])


class DuplicateLeadCheckQuerySet(models.QuerySet):
    def for_network(self, network):
        return self.filter(network=network)

    def exists_for_lead(self, network, lead_id: str) -> bool:
        return self.filter(network=network, lead_id=lead_id).exists()


# ── Managers ──────────────────────────────────────────────────────────────────

class NetworkPostbackConfigManager(models.Manager):
    def get_queryset(self):
        return NetworkPostbackConfigQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def get_by_key_or_raise(self, network_key: str):
        from .exceptions import NetworkNotFoundException, NetworkInactiveException
        from .choices import ValidatorStatus
        try:
            config = self.get(network_key=network_key)
        except self.model.DoesNotExist:
            raise NetworkNotFoundException()
        if config.status != ValidatorStatus.ACTIVE:
            raise NetworkInactiveException(
                detail=f"Network '{config.name}' is not active."
            )
        return config


class PostbackLogManager(models.Manager):
    def get_queryset(self):
        return PostbackLogQuerySet(self.model, using=self._db)

    def retryable(self):
        return self.get_queryset().retryable()

    def is_duplicate(self, network, lead_id: str) -> bool:
        from .choices import PostbackStatus
        return self.filter(
            network=network,
            lead_id=lead_id,
            status__in=[PostbackStatus.REWARDED, PostbackStatus.VALIDATED],
        ).exists()


class DuplicateLeadCheckManager(models.Manager):
    def get_queryset(self):
        return DuplicateLeadCheckQuerySet(self.model, using=self._db)

    def is_duplicate(self, network, lead_id: str) -> bool:
        return self.get_queryset().exists_for_lead(network, lead_id)
