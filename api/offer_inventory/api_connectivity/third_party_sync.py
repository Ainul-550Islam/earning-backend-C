# api/offer_inventory/api_connectivity/third_party_sync.py
"""
Third-Party Sync — External service synchronization.
Syncs offers, conversions, and user data with external platforms.
Supports: Tapjoy, Fyber, AdGem, OfferToro, CPALead, MaxBounty.
"""
import logging
import requests
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ThirdPartySyncManager:
    """Orchestrates synchronization with external offer networks."""

    SUPPORTED_NETWORKS = {
        'tapjoy'    : TapjoySyncer,
        'fyber'     : FyberSyncer,
        'adgem'     : AdGemSyncer,
        'offertoro' : OfferToroSyncer,
        'generic'   : GenericNetworkSyncer,
    }

    @classmethod
    def sync_network(cls, network_slug: str, source) -> dict:
        """Sync a specific network's offers."""
        syncer_class = cls.SUPPORTED_NETWORKS.get(
            network_slug.lower(),
            GenericNetworkSyncer
        )
        syncer = syncer_class(source)
        return syncer.sync()

    @classmethod
    def sync_all(cls, tenant=None) -> dict:
        """Sync all enabled networks."""
        from api.offer_inventory.models import OfferInventorySource

        sources = OfferInventorySource.objects.filter(is_enabled=True)
        if tenant:
            sources = sources.filter(tenant=tenant)

        results = {}
        for source in sources:
            slug = source.network.slug if source.network else 'generic'
            try:
                results[slug] = cls.sync_network(slug, source)
            except Exception as e:
                logger.error(f'Sync failed for {slug}: {e}')
                results[slug] = {'error': str(e)}
        return results


class GenericNetworkSyncer:
    """Base syncer — works with any JSON feed."""

    def __init__(self, source):
        self.source  = source
        self.network = source.network

    def sync(self) -> dict:
        try:
            data   = self._fetch()
            offers = self._parse(data)
            saved  = self._upsert(offers)
            self._update_source(saved)
            return {'synced': saved, 'network': self.network.slug}
        except Exception as e:
            self._mark_error(str(e))
            raise

    def _fetch(self) -> dict:
        resp = requests.get(
            self.source.feed_url,
            headers=self.source.auth_headers or {},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def _parse(self, data) -> list:
        if isinstance(data, list):
            return data
        for key in ('offers', 'data', 'results', 'items'):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []

    def _upsert(self, offers: list) -> int:
        from api.offer_inventory.models import Offer
        count = 0
        for item in offers:
            ext_id = str(item.get('id') or item.get('offer_id', '')).strip()
            if not ext_id:
                continue
            try:
                Offer.objects.update_or_create(
                    external_offer_id=ext_id,
                    network          =self.network,
                    defaults={
                        'title'        : str(item.get('name') or item.get('title', ''))[:255],
                        'description'  : str(item.get('description', ''))[:5000],
                        'offer_url'    : str(item.get('url') or item.get('offer_url', ''))[:2000],
                        'payout_amount': Decimal(str(item.get('payout', 0) or 0)),
                        'status'       : 'active',
                        'tenant'       : self.source.tenant,
                    }
                )
                count += 1
            except Exception as e:
                logger.warning(f'Upsert error ({ext_id}): {e}')
        return count

    def _update_source(self, count: int):
        self.source.last_synced   = timezone.now()
        self.source.offers_pulled = count
        self.source.error_count   = 0
        self.source.last_error    = ''
        self.source.save(update_fields=['last_synced', 'offers_pulled', 'error_count', 'last_error'])

    def _mark_error(self, error: str):
        self.source.error_count += 1
        self.source.last_error   = error[:500]
        self.source.save(update_fields=['error_count', 'last_error'])


class TapjoySyncer(GenericNetworkSyncer):
    """Tapjoy-specific offer sync."""

    def _parse(self, data) -> list:
        items  = data.get('offers', [])
        result = []
        for item in items:
            result.append({
                'id'         : item.get('offer_id', ''),
                'name'       : item.get('offer_name', ''),
                'description': item.get('description', ''),
                'url'        : item.get('offer_url', ''),
                'payout'     : item.get('payout', 0),
            })
        return result


class FyberSyncer(GenericNetworkSyncer):
    """Fyber/Digital Turbine specific sync."""

    def _parse(self, data) -> list:
        items  = data.get('items', [])
        result = []
        for item in items:
            result.append({
                'id'         : item.get('id', ''),
                'name'       : item.get('title', ''),
                'description': item.get('description', ''),
                'url'        : item.get('click_url', ''),
                'payout'     : item.get('amount', 0),
            })
        return result


class AdGemSyncer(GenericNetworkSyncer):
    """AdGem-specific sync."""

    def _parse(self, data) -> list:
        items  = data.get('campaigns', [])
        result = []
        for item in items:
            result.append({
                'id'         : item.get('campaign_id', ''),
                'name'       : item.get('name', ''),
                'description': item.get('requirements', ''),
                'url'        : item.get('tracking_url', ''),
                'payout'     : item.get('payout', 0),
            })
        return result


class OfferToroSyncer(GenericNetworkSyncer):
    """OfferToro-specific sync."""

    def _parse(self, data) -> list:
        items  = data.get('data', {}).get('offers', [])
        result = []
        for item in items:
            result.append({
                'id'         : str(item.get('id', '')),
                'name'       : item.get('name', ''),
                'description': item.get('description', ''),
                'url'        : item.get('offerurl', ''),
                'payout'     : item.get('payout', 0),
            })
        return result
