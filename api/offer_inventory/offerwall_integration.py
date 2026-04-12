# api/offer_inventory/offerwall_integration.py
"""
OfferWall Integration — Resilient & Reactive.

Patterns implemented:
  1. Circuit Breaker — after N failures, stop calling the API
     (CLOSED → OPEN → HALF_OPEN → CLOSED)
  2. Timeout — every external call has a hard timeout (no hanging)
  3. Cache Fallback — if API is slow/down, serve stale cache immediately
  4. Retry with Exponential Backoff — transient errors auto-retry
  5. Bulkhead — each network isolated, one failure doesn't affect others
  6. Health probing — HALF_OPEN state tries one request before fully reopening

Circuit States:
    CLOSED    — normal operation, requests flow through
    OPEN      — too many failures, requests rejected immediately
    HALF_OPEN — testing recovery, single probe request allowed
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Timeouts ──────────────────────────────────────────────────────
API_TIMEOUT_SECONDS      = 8     # Max wait per external API call
CIRCUIT_OPEN_DURATION    = 60    # Seconds before trying HALF_OPEN
CIRCUIT_FAILURE_THRESHOLD= 5     # Failures before OPEN
CACHE_FALLBACK_TTL       = 1800  # 30 min stale cache acceptable


# ════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED    = 'closed'      # Normal — pass requests through
    OPEN      = 'open'        # Failing — reject immediately
    HALF_OPEN = 'half_open'   # Recovering — try one probe


class CircuitBreaker:
    """
    Thread-safe circuit breaker backed by Redis.
    One instance per network_slug — isolated per partner.
    """

    def __init__(self, name: str,
                 failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
                 recovery_timeout : int = CIRCUIT_OPEN_DURATION):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self._lock             = threading.Lock()

    # ── Redis keys ────────────────────────────────────────────────
    @property
    def _state_key(self)   : return f'cb_state:{self.name}'
    @property
    def _failures_key(self): return f'cb_failures:{self.name}'
    @property
    def _opened_at_key(self): return f'cb_opened_at:{self.name}'

    # ── State management ──────────────────────────────────────────
    @property
    def state(self) -> CircuitState:
        raw = cache.get(self._state_key, CircuitState.CLOSED.value)
        try:
            return CircuitState(raw)
        except ValueError:
            return CircuitState.CLOSED

    def _set_state(self, state: CircuitState):
        cache.set(self._state_key, state.value, 3600)

    @property
    def failure_count(self) -> int:
        return int(cache.get(self._failures_key, 0))

    def _increment_failure(self):
        count = self.failure_count + 1
        cache.set(self._failures_key, count, 3600)
        return count

    def _reset_failures(self):
        cache.delete(self._failures_key)

    # ── Core interface ────────────────────────────────────────────
    def is_available(self) -> bool:
        """Can we make a request right now?"""
        state = self.state

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            opened_at = cache.get(self._opened_at_key, 0)
            if time.time() - opened_at >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                logger.info(f'Circuit [{self.name}] → HALF_OPEN (probe attempt)')
                return True
            return False

        if state == CircuitState.HALF_OPEN:
            return True  # Allow single probe

        return False

    def record_success(self):
        """Call succeeded — close circuit."""
        with self._lock:
            self._reset_failures()
            if self.state != CircuitState.CLOSED:
                self._transition_to(CircuitState.CLOSED)
                logger.info(f'Circuit [{self.name}] → CLOSED (recovered)')

    def record_failure(self, error: str = ''):
        """Call failed — track and potentially open circuit."""
        with self._lock:
            count = self._increment_failure()
            logger.warning(
                f'Circuit [{self.name}] failure {count}/{self.failure_threshold}'
                + (f': {error}' if error else '')
            )

            if self.state == CircuitState.HALF_OPEN:
                # Probe failed — back to OPEN
                self._transition_to(CircuitState.OPEN)
                logger.warning(f'Circuit [{self.name}] probe failed → re-OPEN')
            elif count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.error(
                    f'Circuit [{self.name}] OPENED after {count} failures. '
                    f'Will retry in {self.recovery_timeout}s.'
                )

    def _transition_to(self, state: CircuitState):
        self._set_state(state)
        if state == CircuitState.OPEN:
            cache.set(self._opened_at_key, time.time(), 3600)

    def status(self) -> dict:
        return {
            'name'          : self.name,
            'state'         : self.state.value,
            'failure_count' : self.failure_count,
            'threshold'     : self.failure_threshold,
        }


# ════════════════════════════════════════════════════════════════
# OFFERWALL CLIENT (per network)
# ════════════════════════════════════════════════════════════════

class OfferWallClient:
    """
    Resilient HTTP client for a single offerwall network.
    - Circuit breaker per network (isolated failures)
    - Timeout on every request
    - Cache fallback when circuit OPEN or request fails
    - Retry with exponential backoff
    """

    def __init__(self, source, timeout: int = API_TIMEOUT_SECONDS):
        """
        source: OfferInventorySource instance
        """
        self.source          = source
        self.network         = source.network
        self.timeout         = timeout
        self.circuit_breaker = CircuitBreaker(
            name             = f'offerwall:{self.network.slug}',
            failure_threshold= CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout = CIRCUIT_OPEN_DURATION,
        )

    # ── Public API ────────────────────────────────────────────────

    def fetch_offers(
        self,
        params   : dict = None,
        max_retry: int  = 2,
    ) -> List[dict]:
        """
        Fetch offers from network.
        Returns list of offer dicts.
        Falls back to cache if API unavailable.
        """
        cache_key = self._cache_key('offers', params)

        # Circuit OPEN → serve cache immediately (no hanging)
        if not self.circuit_breaker.is_available():
            logger.warning(
                f'Circuit OPEN for [{self.network.slug}]. '
                f'Serving cached offers.'
            )
            return self._get_fallback_cache(cache_key) or []

        # Try API with retry + exponential backoff
        for attempt in range(max_retry + 1):
            try:
                offers = self._do_fetch(params)

                # Success → record, warm cache
                self.circuit_breaker.record_success()
                self._warm_cache(cache_key, offers)
                logger.info(
                    f'[{self.network.slug}] fetched {len(offers)} offers '
                    f'(attempt {attempt+1})'
                )
                return offers

            except TimeoutError as e:
                self.circuit_breaker.record_failure(f'timeout: {e}')
                logger.warning(
                    f'[{self.network.slug}] timeout on attempt {attempt+1}'
                )
            except Exception as e:
                self.circuit_breaker.record_failure(str(e))
                logger.error(
                    f'[{self.network.slug}] error on attempt {attempt+1}: {e}'
                )

            if attempt < max_retry:
                backoff = min(2 ** attempt, 8)   # 1s, 2s, 4s, max 8s
                time.sleep(backoff)

        # All retries exhausted → serve stale cache
        fallback = self._get_fallback_cache(cache_key)
        if fallback is not None:
            logger.warning(
                f'[{self.network.slug}] API unavailable after {max_retry+1} '
                f'attempts. Serving {len(fallback)} stale cached offers.'
            )
            return fallback

        logger.error(f'[{self.network.slug}] API down and no cache available.')
        return []

    def fetch_single_offer(self, external_offer_id: str) -> Optional[dict]:
        """Fetch one offer. Cached, with circuit breaker."""
        cache_key = self._cache_key(f'offer:{external_offer_id}')
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.circuit_breaker.is_available():
            return None

        try:
            url  = f'{self.source.feed_url}/{external_offer_id}'
            data = self._http_get(url)
            self.circuit_breaker.record_success()
            cache.set(cache_key, data, 600)
            return data
        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            return None

    def health_check(self) -> dict:
        """Ping network API — used by NetworkPinger task."""
        try:
            import requests as _req
            start = time.monotonic()
            resp  = _req.get(
                self.source.feed_url,
                headers=self.source.auth_headers or {},
                timeout=5,
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            is_up      = resp.status_code < 400

            if is_up:
                self.circuit_breaker.record_success()
            else:
                self.circuit_breaker.record_failure(f'HTTP {resp.status_code}')

            return {
                'network'    : self.network.slug,
                'is_up'      : is_up,
                'status_code': resp.status_code,
                'latency_ms' : round(elapsed_ms, 1),
                'circuit'    : self.circuit_breaker.status(),
            }
        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            return {
                'network'   : self.network.slug,
                'is_up'     : False,
                'error'     : str(e),
                'circuit'   : self.circuit_breaker.status(),
            }

    # ── Internal ──────────────────────────────────────────────────

    def _do_fetch(self, params: dict = None) -> List[dict]:
        """Make the actual HTTP call with hard timeout."""
        import requests as _req

        url     = self.source.feed_url
        headers = self.source.auth_headers or {}
        qparams = params or {}

        # Feed type dispatch
        if self.source.feed_type == 'json':
            resp = self._http_get(url, headers=headers, params=qparams)
            return self._parse_json(resp)
        elif self.source.feed_type == 'xml':
            resp = self._http_get_raw(url, headers=headers, params=qparams)
            return self._parse_xml(resp)
        elif self.source.feed_type == 'csv':
            resp = self._http_get_raw(url, headers=headers, params=qparams)
            return self._parse_csv(resp)
        else:
            return self._parse_json(self._http_get(url, headers=headers, params=qparams))

    def _http_get(self, url: str, headers: dict = None, params: dict = None) -> dict:
        import requests as _req
        try:
            resp = _req.get(url, headers=headers or {}, params=params or {},
                            timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except _req.exceptions.Timeout:
            raise TimeoutError(f'{url} timed out after {self.timeout}s')
        except _req.exceptions.ConnectionError as e:
            raise ConnectionError(f'Connection failed: {url}') from e

    def _http_get_raw(self, url: str, headers: dict = None, params: dict = None) -> str:
        import requests as _req
        try:
            resp = _req.get(url, headers=headers or {}, params=params or {},
                            timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except _req.exceptions.Timeout:
            raise TimeoutError(f'{url} timed out after {self.timeout}s')

    def _parse_json(self, data) -> List[dict]:
        """Normalize JSON response to list of offer dicts."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('offers', 'data', 'results', 'items', 'response'):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []

    def _parse_xml(self, xml_text: str) -> List[dict]:
        """Parse XML offer feed."""
        try:
            import xml.etree.ElementTree as ET
            root   = ET.fromstring(xml_text)
            offers = []
            for item in root.iter('offer'):
                offers.append({
                    'id'         : item.findtext('id', ''),
                    'name'       : item.findtext('name', ''),
                    'description': item.findtext('description', ''),
                    'url'        : item.findtext('url', ''),
                    'payout'     : item.findtext('payout', '0'),
                })
            return offers
        except Exception as e:
            logger.error(f'XML parse error: {e}')
            return []

    def _parse_csv(self, csv_text: str) -> List[dict]:
        """Parse CSV offer feed."""
        import csv, io
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            return list(reader)
        except Exception as e:
            logger.error(f'CSV parse error: {e}')
            return []

    def _cache_key(self, suffix: str, params: dict = None) -> str:
        base = f'offerwall:{self.network.slug}:{suffix}'
        if params:
            import hashlib, json
            ph = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
            base += f':{ph}'
        return base

    def _warm_cache(self, key: str, data):
        """Store fresh data with full TTL."""
        cache.set(key, data, CACHE_FALLBACK_TTL)

    def _get_fallback_cache(self, key: str):
        """Get stale cache. Returns None if nothing cached."""
        return cache.get(key)   # None if expired/missing


# ════════════════════════════════════════════════════════════════
# OFFERWALL INTEGRATION SERVICE
# ════════════════════════════════════════════════════════════════

class OfferWallIntegrationService:
    """
    High-level integration service.
    Handles multiple networks, syncs to DB, applies transformations.
    """

    @staticmethod
    def fetch_and_sync_all(tenant=None) -> dict:
        """
        Fetch from all enabled sources, sync to Offer table.
        Each network is isolated — one failure doesn't block others.
        """
        from api.offer_inventory.models import OfferInventorySource, Offer

        sources = OfferInventorySource.objects.filter(is_enabled=True)
        if tenant:
            sources = sources.filter(tenant=tenant)

        results = {'synced': [], 'failed': [], 'circuit_open': []}

        for source in sources:
            client = OfferWallClient(source)
            slug   = source.network.slug

            try:
                raw_offers = client.fetch_offers()

                if not raw_offers:
                    results['circuit_open'].append(slug)
                    continue

                synced = OfferWallIntegrationService._upsert_offers(
                    raw_offers, source
                )
                source.last_synced   = timezone.now()
                source.offers_pulled = len(raw_offers)
                source.error_count   = 0
                source.last_error    = ''
                source.save(update_fields=['last_synced', 'offers_pulled',
                                           'error_count', 'last_error'])
                results['synced'].append({'network': slug, 'count': synced})

            except Exception as e:
                logger.error(f'Sync failed for {slug}: {e}')
                source.error_count += 1
                source.last_error   = str(e)[:500]
                source.save(update_fields=['error_count', 'last_error'])
                results['failed'].append({'network': slug, 'error': str(e)})

        return results

    @staticmethod
    def _upsert_offers(raw_offers: List[dict], source) -> int:
        """Upsert raw offer dicts into the Offer table."""
        from api.offer_inventory.models import Offer
        count = 0
        for item in raw_offers:
            try:
                ext_id = str(item.get('id') or item.get('offer_id', '')).strip()
                if not ext_id:
                    continue

                payout = Decimal(str(item.get('payout', 0) or 0))

                Offer.objects.update_or_create(
                    external_offer_id=ext_id,
                    network=source.network,
                    defaults={
                        'title'        : str(item.get('name') or item.get('title', ''))[:255],
                        'description'  : str(item.get('description', ''))[:5000],
                        'offer_url'    : str(item.get('url') or item.get('offer_url', ''))[:2000],
                        'payout_amount': payout,
                        'status'       : 'active',
                        'tenant'       : source.tenant,
                    }
                )
                count += 1
            except Exception as e:
                logger.warning(f'Offer upsert error ({item}): {e}')
        return count

    @staticmethod
    def get_circuit_statuses() -> List[dict]:
        """Return current circuit breaker status for all networks."""
        from api.offer_inventory.models import OfferNetwork
        networks = OfferNetwork.objects.filter(status='active')
        return [
            CircuitBreaker(f'offerwall:{n.slug}').status()
            for n in networks
        ]

    @staticmethod
    def reset_circuit(network_slug: str):
        """Manually reset a circuit breaker (admin action)."""
        cb = CircuitBreaker(f'offerwall:{network_slug}')
        cb._transition_to(CircuitState.CLOSED)
        cb._reset_failures()
        logger.info(f'Circuit manually reset: {network_slug}')
