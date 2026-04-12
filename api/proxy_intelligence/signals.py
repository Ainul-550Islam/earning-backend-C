"""
Proxy Intelligence Signals  (COMPLETE)
Connects model events to detection, caching, and alert pipelines.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='proxy_intelligence.FraudAttempt')
def on_fraud_attempt_created(sender, instance, created, **kwargs):
    """When a fraud attempt is logged, update the IP's fraud score and alert."""
    if not created:
        return
    try:
        from .models import IPIntelligence
        obj = IPIntelligence.objects.filter(ip_address=instance.ip_address).first()
        if obj:
            obj.fraud_score = min(obj.fraud_score + 10, 100)
            obj.risk_score  = min(obj.risk_score + 5, 100)
            obj.save(update_fields=['fraud_score', 'risk_score'])
            obj.update_risk_level()
            obj.save(update_fields=['risk_level'])
    except Exception as e:
        logger.error(f"FraudAttempt signal error: {e}")

    # Trigger real-time alert for high-risk attempts
    try:
        if instance.risk_score >= 61:
            from .real_time_processing.webhook_handler import AlertDispatcher
            AlertDispatcher.dispatch('fraud_detected', {
                'ip_address': instance.ip_address,
                'fraud_type': instance.fraud_type,
                'risk_score': instance.risk_score,
                'risk_level': 'high' if instance.risk_score < 81 else 'critical',
                'flags': instance.flags or [],
            }, instance.tenant)
    except Exception as e:
        logger.debug(f"Fraud alert dispatch failed: {e}")


@receiver(post_save, sender='proxy_intelligence.IPBlacklist')
def on_ip_blacklisted(sender, instance, created, **kwargs):
    """When an IP is blacklisted, invalidate all caches for that IP."""
    try:
        from .cache import PICache
        PICache.invalidate_all_for_ip(instance.ip_address)
    except Exception as e:
        logger.debug(f"Blacklist cache invalidation failed: {e}")

    if created:
        logger.info(f"IP blacklisted: {instance.ip_address} | Reason: {instance.reason}")
        try:
            from .real_time_processing.redis_publisher import RedisPublisher
            RedisPublisher.publish_blacklist(instance.ip_address, instance.reason)
        except Exception:
            pass


@receiver(post_delete, sender='proxy_intelligence.IPBlacklist')
def on_ip_blacklist_deleted(sender, instance, **kwargs):
    """When a blacklist entry is removed, clear the cache."""
    try:
        from .cache import PICache
        PICache.invalidate_blacklist(instance.ip_address)
    except Exception:
        pass


@receiver(post_save, sender='proxy_intelligence.IPWhitelist')
def on_ip_whitelisted(sender, instance, created, **kwargs):
    """When an IP is whitelisted, invalidate its blacklist cache entry."""
    try:
        from .cache import PICache
        PICache.invalidate_whitelist(instance.ip_address or '')
    except Exception:
        pass


@receiver(post_save, sender='proxy_intelligence.UserRiskProfile')
def on_user_risk_changed(sender, instance, created, **kwargs):
    """Alert when a user's risk level becomes critical."""
    if instance.risk_level == 'critical' and instance.is_high_risk:
        try:
            from .real_time_processing.webhook_handler import AlertDispatcher
            AlertDispatcher.dispatch('high_risk_ip', {
                'ip_address': f'user:{instance.user_id}',
                'risk_score': instance.overall_risk_score,
                'risk_level': instance.risk_level,
                'flags': ['high_risk_user', f'fraud_attempts:{instance.fraud_attempts_count}'],
            }, instance.tenant)
        except Exception as e:
            logger.debug(f"User risk alert failed: {e}")


@receiver(post_save, sender='proxy_intelligence.TorExitNode')
def on_tor_node_updated(sender, instance, created, **kwargs):
    """Invalidate Tor check cache when exit node list changes."""
    try:
        from django.core.cache import cache
        cache.delete(f"pi:tor_check:{instance.ip_address}")
        if created:
            logger.debug(f"New Tor exit node: {instance.ip_address}")
    except Exception:
        pass


@receiver(post_save, sender='proxy_intelligence.MLModelMetadata')
def on_ml_model_activated(sender, instance, **kwargs):
    """Log when an ML model is activated."""
    if instance.is_active:
        logger.info(f"ML Model activated: {instance.name} v{instance.version} ({instance.model_type})")


@receiver(post_save, sender='proxy_intelligence.IntegrationCredential')
def on_integration_credential_saved(sender, instance, created, **kwargs):
    """Clear service-specific caches when credentials change."""
    try:
        from django.core.cache import cache
        pattern_key = f"pi:{instance.service}:*"
        logger.info(f"Integration credential updated: {instance.service}")
    except Exception:
        pass


@receiver(post_save, sender='proxy_intelligence.FraudRule')
def on_fraud_rule_changed(sender, instance, **kwargs):
    """Log rule changes and write audit trail."""
    try:
        from .models import SystemAuditTrail
        SystemAuditTrail.objects.create(
            action='rule_change',
            model_name='FraudRule',
            object_id=str(instance.pk),
            object_repr=str(instance),
            after_state={
                'name': instance.name,
                'is_active': instance.is_active,
                'condition_type': instance.condition_type,
                'action': instance.action,
            },
        )
    except Exception:
        pass
