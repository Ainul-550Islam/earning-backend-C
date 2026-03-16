# api/promotions/connectors/rtb_exchange.py
# RTB Exchange — OpenRTB bid request/response to external DSPs
import json, logging, requests
from dataclasses import dataclass
from decimal import Decimal
from django.conf import settings
logger = logging.getLogger('connectors.rtb')

@dataclass
class ExternalBidResponse:
    dsp_name: str; campaign_id: str; bid_price: Decimal; ad_markup: str; status: str

class RTBExchangeConnector:
    """Send bid requests to external DSPs (Demand Side Platforms)。"""
    DSPS = {
        'google_adx':   'https://googleads.g.doubleclick.net/rtb/bid',
        'appnexus':     'https://ib.adnxs.com/openrtb2',
        'pubmatic':     'https://openbid.pubmatic.com/translator',
    }
    TIMEOUT_MS = 80   # 80ms RTB timeout

    def broadcast_bid_request(self, bid_request: dict) -> list[ExternalBidResponse]:
        """All configured DSPs কে bid request পাঠায়।"""
        import concurrent.futures
        responses = []
        dsps      = {k: v for k, v in self.DSPS.items() if getattr(settings, f'RTB_{k.upper()}_ENABLED', False)}

        def call_dsp(name, url):
            try:
                r = requests.post(url, json=bid_request, timeout=self.TIMEOUT_MS/1000, headers={'Content-Type': 'application/json'})
                if r.status_code == 204: return ExternalBidResponse(name, '', Decimal('0'), '', 'no_bid')
                d = r.json()
                price = Decimal(str(d.get('seatbid',[{}])[0].get('bid',[{}])[0].get('price',0)))
                return ExternalBidResponse(name, d.get('id',''), price, '', 'bid')
            except Exception as e:
                return ExternalBidResponse(name, '', Decimal('0'), '', f'error:{str(e)[:50]}')

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(call_dsp, n, u): n for n, u in dsps.items()}
            for f in concurrent.futures.as_completed(futures, timeout=0.1):
                try: responses.append(f.result())
                except Exception: pass
        return responses

    def select_winner(self, responses: list[ExternalBidResponse], floor: Decimal) -> ExternalBidResponse | None:
        bids = [r for r in responses if r.status == 'bid' and r.bid_price >= floor]
        return max(bids, key=lambda r: r.bid_price) if bids else None
