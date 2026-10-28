# =============================================================================
# fraud_detection/views_caching.py
# =============================================================================
"""
Cache-enabled API views that wire caching.py (previously floating) to the
most DB-heavy endpoints.

RedisCacheManager, RiskScoreCache, FraudRuleCache, IPReputationCache — all
defined in caching.py but never called from any view. This module exposes:

  Cache management:
    GET  /fraud/cache/stats/               → cache hit/miss stats
    POST /fraud/cache/invalidate/          → manual cache invalidation
    POST /fraud/cache/warmup/              → pre-warm critical caches
    POST /fraud/cache/clear/               → clear all fraud caches (admin only)
    GET  /fraud/cache/keys/                → list cached keys + TTLs

  Cache-backed read endpoints (replaces direct DB on hot paths):
    GET  /fraud/cache/risk-score/<user_id>/   → RiskScoreCache.get()
    GET  /fraud/cache/rules/                  → FraudRuleCache.get_active()
    GET  /fraud/cache/ip/<ip_address>/        → IPReputationCache.get()
    GET  /fraud/cache/whitelist/              → WhitelistCache.get_all()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.core.cache import cache as django_cache
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)

logger = logging.getLogger(__name__)


def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _get_cache_mgr():
    """Lazy-load RedisCacheManager from caching.py."""
    try:
        from api.fraud_detection.caching import get_redis_cache_manager
        return get_redis_cache_manager()
    except ImportError:
        return None


def _get_risk_score_cache():
    try:
        from api.fraud_detection.caching import RiskScoreCache
        return RiskScoreCache()
    except ImportError:
        return None


def _get_fraud_rule_cache():
    try:
        from api.fraud_detection.caching import FraudRuleCache
        return FraudRuleCache()
    except ImportError:
        return None


def _get_ip_reputation_cache():
    try:
        from api.fraud_detection.caching import IPReputationCache
        return IPReputationCache()
    except ImportError:
        return None


def _get_whitelist_cache():
    try:
        from api.fraud_detection.caching import WhitelistCache
        return WhitelistCache()
    except ImportError:
        return None


# =============================================================================
# 1. Cache management
# =============================================================================

class CacheStatsAPIView(APIView):
    """
    GET /fraud/cache/stats/

    Return cache hit/miss rates, key counts, memory usage.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        mgr = _get_cache_mgr()
        if mgr is None:
            return _err('caching.py not available.', status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            stats = mgr.get_statistics() if hasattr(mgr, 'get_statistics') else {}
            # Also include Django cache info if redis
            try:
                client = django_cache.client.get_client()
                info   = client.info('stats')
                stats['redis_hits']   = info.get('keyspace_hits', 0)
                stats['redis_misses'] = info.get('keyspace_misses', 0)
                stats['redis_memory'] = info.get('used_memory_human', 'N/A')
            except Exception:
                pass
            return _ok(stats)
        except Exception as exc:
            logger.exception('CacheStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CacheInvalidateAPIView(APIView):
    """
    POST /fraud/cache/invalidate/

    Invalidate one or more specific cache keys.
    Body: {
        key_type (str): risk_score | fraud_rule | ip_reputation | whitelist | all
        entity_id (str, optional): user_id / ip_address / rule_id for targeted bust
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        key_type  = request.data.get('key_type', 'all')
        entity_id = request.data.get('entity_id')

        valid_types = ('risk_score', 'fraud_rule', 'ip_reputation', 'whitelist', 'all')
        if key_type not in valid_types:
            return _err(f"key_type must be one of: {', '.join(valid_types)}")

        try:
            mgr       = _get_cache_mgr()
            deleted   = 0

            if key_type in ('risk_score', 'all'):
                rc = _get_risk_score_cache()
                if rc and entity_id:
                    rc.invalidate(user_id=entity_id)
                    deleted += 1
                elif rc and hasattr(rc, 'invalidate_all'):
                    deleted += rc.invalidate_all()

            if key_type in ('fraud_rule', 'all'):
                frc = _get_fraud_rule_cache()
                if frc and hasattr(frc, 'invalidate_all'):
                    deleted += frc.invalidate_all()

            if key_type in ('ip_reputation', 'all'):
                irc = _get_ip_reputation_cache()
                if irc and entity_id:
                    irc.invalidate(ip_address=entity_id)
                    deleted += 1
                elif irc and hasattr(irc, 'invalidate_all'):
                    deleted += irc.invalidate_all()

            if key_type in ('whitelist', 'all'):
                wc = _get_whitelist_cache()
                if wc and hasattr(wc, 'invalidate_all'):
                    deleted += wc.invalidate_all()

            # Fallback: use manager
            if mgr and hasattr(mgr, 'invalidate'):
                mgr.invalidate(key_type=key_type, entity_id=entity_id)

            logger.info(
                "Cache invalidated: key_type=%s entity_id=%s by user %s (deleted≈%d)",
                key_type, entity_id, request.user.id, deleted,
            )
            return _ok({
                'invalidated':  True,
                'key_type':     key_type,
                'entity_id':    entity_id,
                'keys_deleted': deleted,
            })
        except Exception as exc:
            logger.exception('CacheInvalidateAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CacheWarmupAPIView(APIView):
    """
    POST /fraud/cache/warmup/

    Pre-warm frequently accessed caches.
    Body: { targets: [fraud_rules, high_risk_profiles, active_whitelist] }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        targets = request.data.get(
            'targets', ['fraud_rules', 'high_risk_profiles', 'active_whitelist']
        )
        results = {}

        try:
            mgr = _get_cache_mgr()

            if 'fraud_rules' in targets:
                try:
                    frc = _get_fraud_rule_cache()
                    if frc and hasattr(frc, 'warmup'):
                        count = frc.warmup()
                        results['fraud_rules'] = {'warmed': count}
                    elif mgr and hasattr(mgr, 'warmup_fraud_rules'):
                        mgr.warmup_fraud_rules()
                        results['fraud_rules'] = {'warmed': True}
                except Exception as exc:
                    results['fraud_rules'] = {'error': str(exc)}

            if 'high_risk_profiles' in targets:
                try:
                    from api.fraud_detection.models import UserRiskProfile
                    from api.fraud_detection.serializers import UserRiskProfileSerializer
                    profiles = UserRiskProfile.objects.filter(
                        overall_risk_score__gte=70, is_flagged=True
                    ).select_related('user')[:200]
                    warmed = 0
                    rc = _get_risk_score_cache()
                    for p in profiles:
                        if rc and hasattr(rc, 'set'):
                            rc.set(user_id=p.user_id, score=p.overall_risk_score)
                            warmed += 1
                        else:
                            django_cache.set(
                                f'risk_score:{p.user_id}',
                                p.overall_risk_score,
                                timeout=1800,
                            )
                            warmed += 1
                    results['high_risk_profiles'] = {'warmed': warmed}
                except Exception as exc:
                    results['high_risk_profiles'] = {'error': str(exc)}

            if 'active_whitelist' in targets:
                try:
                    from api.fraud_detection.models import FraudWhitelist
                    entries = list(
                        FraudWhitelist.objects.filter(is_active=True)
                        .values('entity_type', 'entity_value')[:500]
                    )
                    for entry in entries:
                        key = f"whitelist:{entry['entity_type']}:{entry['entity_value']}"
                        django_cache.set(key, True, timeout=3600)
                    results['active_whitelist'] = {'warmed': len(entries)}
                except Exception as exc:
                    results['active_whitelist'] = {'error': str(exc)}

            logger.info("Cache warmup completed: %s by user %s", results, request.user.id)
            return _ok({'warmed': True, 'targets': targets, 'results': results})
        except Exception as exc:
            logger.exception('CacheWarmupAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CacheClearAPIView(APIView):
    """
    POST /fraud/cache/clear/

    Clear ALL fraud detection caches. Admin only. Use with caution.
    Body: { confirm: "CLEAR_ALL_FRAUD_CACHES" }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        confirm = request.data.get('confirm', '')
        if confirm != 'CLEAR_ALL_FRAUD_CACHES':
            return _err(
                'Send { "confirm": "CLEAR_ALL_FRAUD_CACHES" } to confirm.',
                status.HTTP_400_BAD_REQUEST,
            )
        try:
            mgr     = _get_cache_mgr()
            deleted = 0

            if mgr and hasattr(mgr, 'clear_all'):
                deleted = mgr.clear_all()
            else:
                # Fallback: scan and delete fraud:* keys from Redis
                try:
                    client = django_cache.client.get_client()
                    keys   = list(client.scan_iter('fraud:*')) + \
                             list(client.scan_iter('vel:*'))   + \
                             list(client.scan_iter('risk_score:*')) + \
                             list(client.scan_iter('whitelist:*')) + \
                             list(client.scan_iter('ip_rep:*')) + \
                             list(client.scan_iter('biometrics:*')) + \
                             list(client.scan_iter('ref_*'))
                    if keys:
                        deleted = len(keys)
                        for key in keys:
                            client.delete(key)
                except Exception:
                    deleted = -1  # unknown

            logger.warning(
                "Fraud detection cache CLEARED by user %s. Keys deleted: %s",
                request.user.id, deleted,
            )
            return _ok({'cleared': True, 'keys_deleted': deleted,
                        'cleared_at': timezone.now().isoformat()})
        except Exception as exc:
            logger.exception('CacheClearAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CacheKeysAPIView(APIView):
    """
    GET /fraud/cache/keys/?prefix=fraud&limit=100

    List cached keys with their remaining TTL.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        prefix = request.query_params.get('prefix', 'fraud')
        limit  = int(request.query_params.get('limit', 100))

        try:
            client = django_cache.client.get_client()
            raw_keys = list(client.scan_iter(f'{prefix}:*'))[:limit]
            result   = []
            for key in raw_keys:
                ttl = client.ttl(key)
                result.append({
                    'key': key.decode() if isinstance(key, bytes) else key,
                    'ttl': ttl,
                })
            result.sort(key=lambda x: x['ttl'])
            return _ok({'count': len(result), 'prefix': prefix, 'keys': result})
        except Exception as exc:
            logger.exception('CacheKeysAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 2. Cache-backed hot read endpoints
# =============================================================================

class CachedRiskScoreAPIView(APIView):
    """
    GET /fraud/cache/risk-score/<user_id>/

    Returns user risk score from Redis cache first.
    Falls back to DB if cache miss, then stores result.
    Cache TTL: 30 minutes (configurable via CACHE_TTL.user_risk_profile).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, user_id: int):
        if not request.user.is_staff and request.user.id != user_id:
            return _err('Permission denied.', status.HTTP_403_FORBIDDEN)

        from django.conf import settings as _settings
        ttl = getattr(_settings, 'CACHE_TTL', {}).get('user_risk_profile', 1800)

        # ── 1. Try RiskScoreCache ─────────────────────────────────────────────
        rc = _get_risk_score_cache()
        if rc and hasattr(rc, 'get'):
            try:
                cached = rc.get(user_id=user_id)
                if cached is not None:
                    return _ok({
                        'user_id':    user_id,
                        'risk_score': cached,
                        'source':     'cache',
                        'cached_at':  None,
                    })
            except Exception as exc:
                logger.debug("RiskScoreCache.get failed, going to DB: %s", exc)

        # ── 2. Fallback: django_cache ──────────────────────────────────────────
        cache_key = f'risk_score:{user_id}'
        cached_score = django_cache.get(cache_key)
        if cached_score is not None:
            return _ok({
                'user_id':    user_id,
                'risk_score': cached_score,
                'source':     'django_cache',
            })

        # ── 3. DB hit ──────────────────────────────────────────────────────────
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.get(user_id=user_id)
            score   = profile.overall_risk_score

            # Store in cache
            if rc and hasattr(rc, 'set'):
                rc.set(user_id=user_id, score=score)
            else:
                django_cache.set(cache_key, score, timeout=ttl)

            return _ok({
                'user_id':    user_id,
                'risk_score': score,
                'risk_level': profile.monitoring_level,
                'is_flagged': profile.is_flagged,
                'source':     'db',
            })
        except Exception as exc:
            logger.exception('CachedRiskScoreAPIView DB fallback failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CachedFraudRulesAPIView(APIView):
    """
    GET /fraud/cache/rules/?active_only=true

    Returns active fraud rules from Redis cache.
    Cache TTL: 15 minutes (CACHE_TTL.fraud_rule).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        active_only = request.query_params.get('active_only', 'true').lower() == 'true'

        from django.conf import settings as _settings
        ttl = getattr(_settings, 'CACHE_TTL', {}).get('fraud_rule', 900)
        cache_key = f'fraud:rules:{"active" if active_only else "all"}'

        # ── 1. Try FraudRuleCache ─────────────────────────────────────────────
        frc = _get_fraud_rule_cache()
        if frc and hasattr(frc, 'get_active'):
            try:
                rules = frc.get_active() if active_only else frc.get_all()
                if rules is not None:
                    return _ok({
                        'count':  len(rules),
                        'rules':  rules,
                        'source': 'fraud_rule_cache',
                    })
            except Exception as exc:
                logger.debug("FraudRuleCache.get failed: %s", exc)

        # ── 2. Fallback django_cache ───────────────────────────────────────────
        cached = django_cache.get(cache_key)
        if cached is not None:
            return _ok({'count': len(cached), 'rules': cached, 'source': 'django_cache'})

        # ── 3. DB ──────────────────────────────────────────────────────────────
        try:
            from api.fraud_detection.models import FraudRule
            from api.fraud_detection.serializers import FraudRuleSerializer
            qs    = FraudRule.objects.filter(is_active=True) if active_only \
                    else FraudRule.objects.all()
            rules = FraudRuleSerializer(qs.order_by('-severity'), many=True).data
            rules_list = list(rules)
            if frc and hasattr(frc, 'set_all'):
                frc.set_all(rules_list)
            else:
                django_cache.set(cache_key, rules_list, timeout=ttl)
            return _ok({'count': len(rules_list), 'rules': rules_list, 'source': 'db'})
        except Exception as exc:
            logger.exception('CachedFraudRulesAPIView DB fallback failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CachedIPReputationAPIView(APIView):
    """
    GET /fraud/cache/ip/<ip_address>/

    Returns IP reputation from Redis cache.
    Cache TTL: 1 hour (CACHE_TTL.ip_reputation).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, ip_address: str):
        from django.conf import settings as _settings
        ttl       = getattr(_settings, 'CACHE_TTL', {}).get('ip_reputation', 3600)
        cache_key = f'ip_rep:{ip_address}'

        # ── 1. IPReputationCache ──────────────────────────────────────────────
        irc = _get_ip_reputation_cache()
        if irc and hasattr(irc, 'get'):
            try:
                cached = irc.get(ip_address=ip_address)
                if cached is not None:
                    return _ok({**cached, 'source': 'ip_reputation_cache'})
            except Exception as exc:
                logger.debug("IPReputationCache.get failed: %s", exc)

        # ── 2. Django cache ───────────────────────────────────────────────────
        cached = django_cache.get(cache_key)
        if cached is not None:
            return _ok({**cached, 'source': 'django_cache'})

        # ── 3. DB ─────────────────────────────────────────────────────────────
        try:
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            try:
                rep  = IPReputation.objects.get(ip_address=ip_address)
                data = IPReputationSerializer(rep).data
                data_dict = dict(data)
                if irc and hasattr(irc, 'set'):
                    irc.set(ip_address=ip_address, data=data_dict)
                else:
                    django_cache.set(cache_key, data_dict, timeout=ttl)
                return _ok({**data_dict, 'source': 'db'})
            except IPReputation.DoesNotExist:
                return _ok({
                    'ip_address': ip_address,
                    'known':      False,
                    'fraud_score': 0,
                    'source':     'not_found',
                })
        except Exception as exc:
            logger.exception('CachedIPReputationAPIView DB fallback failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CachedWhitelistAPIView(APIView):
    """
    GET  /fraud/cache/whitelist/?entity_type=ip
    POST /fraud/cache/whitelist/check/   — check a single entity
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        entity_type = request.query_params.get('entity_type')
        cache_key   = f'fraud:whitelist:{entity_type or "all"}'

        cached = django_cache.get(cache_key)
        if cached is not None:
            return _ok({'source': 'cache', 'count': len(cached), 'entries': cached})

        try:
            from api.fraud_detection.models import FraudWhitelist
            qs = FraudWhitelist.objects.filter(is_active=True)
            if entity_type:
                qs = qs.filter(entity_type=entity_type)
            entries = list(qs.values('entity_type', 'entity_value', 'expires_at')[:1000])
            django_cache.set(cache_key, entries, timeout=3600)
            return _ok({'source': 'db', 'count': len(entries), 'entries': entries})
        except Exception as exc:
            logger.exception('CachedWhitelistAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CachedWhitelistCheckAPIView(APIView):
    """
    POST /fraud/cache/whitelist/check/
    Body: { entity_type, entity_value }
    Returns from Redis cache — O(1) lookup.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        entity_type  = request.data.get('entity_type', '').strip()
        entity_value = request.data.get('entity_value', '').strip()
        if not entity_type or not entity_value:
            return _err('entity_type and entity_value required.')

        cache_key = f'whitelist:{entity_type}:{entity_value}'

        # ── 1. Redis direct lookup ────────────────────────────────────────────
        wc = _get_whitelist_cache()
        if wc and hasattr(wc, 'is_whitelisted'):
            try:
                is_wl = wc.is_whitelisted(entity_type=entity_type, entity_value=entity_value)
                return _ok({
                    'entity_type':    entity_type,
                    'entity_value':   entity_value,
                    'is_whitelisted': is_wl,
                    'source':         'whitelist_cache',
                })
            except Exception:
                pass

        cached = django_cache.get(cache_key)
        if cached is not None:
            return _ok({
                'entity_type':    entity_type,
                'entity_value':   entity_value,
                'is_whitelisted': bool(cached),
                'source':         'django_cache',
            })

        # ── 2. DB lookup + cache store ────────────────────────────────────────
        try:
            from api.fraud_detection.models import FraudWhitelist
            from django.utils import timezone as tz
            is_wl = FraudWhitelist.objects.filter(
                entity_type=entity_type,
                entity_value=entity_value,
                is_active=True,
            ).filter(
                models_Q := __import__(
                    'django.db.models', fromlist=['Q']
                ).Q(expires_at__isnull=True) |
                __import__('django.db.models', fromlist=['Q']).Q(expires_at__gt=tz.now())
            ).exists()
            django_cache.set(cache_key, is_wl, timeout=3600)
            return _ok({
                'entity_type':    entity_type,
                'entity_value':   entity_value,
                'is_whitelisted': is_wl,
                'source':         'db',
            })
        except Exception as exc:
            logger.exception('CachedWhitelistCheckAPIView DB failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CachedWhitelistCheckSimpleAPIView(APIView):
    """
    POST /fraud/cache/whitelist/check/ (simplified version that avoids walrus operator)
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        entity_type  = request.data.get('entity_type', '').strip()
        entity_value = request.data.get('entity_value', '').strip()
        if not entity_type or not entity_value:
            return _err('entity_type and entity_value required.')

        cache_key = f'whitelist:{entity_type}:{entity_value}'

        # 1. WhitelistCache
        wc = _get_whitelist_cache()
        if wc and hasattr(wc, 'is_whitelisted'):
            try:
                is_wl = wc.is_whitelisted(
                    entity_type=entity_type, entity_value=entity_value
                )
                return _ok({
                    'entity_type':    entity_type,
                    'entity_value':   entity_value,
                    'is_whitelisted': is_wl,
                    'source':         'whitelist_cache',
                })
            except Exception:
                pass

        # 2. Django cache
        cached = django_cache.get(cache_key)
        if cached is not None:
            return _ok({
                'entity_type':    entity_type,
                'entity_value':   entity_value,
                'is_whitelisted': bool(cached),
                'source':         'django_cache',
            })

        # 3. DB
        try:
            from django.db.models import Q
            from django.utils import timezone as tz
            from api.fraud_detection.models import FraudWhitelist

            is_wl = FraudWhitelist.objects.filter(
                entity_type=entity_type,
                entity_value=entity_value,
                is_active=True,
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
            ).exists()
            django_cache.set(cache_key, is_wl, timeout=3600)
            return _ok({
                'entity_type':    entity_type,
                'entity_value':   entity_value,
                'is_whitelisted': is_wl,
                'source':         'db',
            })
        except Exception as exc:
            logger.exception('CachedWhitelistCheckSimpleAPIView DB failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
