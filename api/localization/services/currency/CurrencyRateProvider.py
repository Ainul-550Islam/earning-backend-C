# services/currency/CurrencyRateProvider.py
"""Exchange rate data providers — OpenExchange/Fixer/ECB"""
import logging
from decimal import Decimal
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CurrencyRateProvider:
    """Multiple exchange rate API providers"""

    def fetch_rates(self, base_currency: str = 'USD', provider: str = 'exchangerate-api') -> Dict:
        """Selected provider থেকে all rates fetch করে"""
        fetchers = {
            'exchangerate-api': self._fetch_exchangerate_api,
            'ecb': self._fetch_ecb,
            'openexchangerates': self._fetch_openexchangerates,
        }
        fetcher = fetchers.get(provider, self._fetch_exchangerate_api)
        return fetcher(base_currency)

    def _fetch_exchangerate_api(self, base: str) -> Dict:
        try:
            import urllib.request, json
            url = f"https://api.exchangerate-api.com/v4/latest/{base}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            return {'success': True, 'base': base, 'rates': data.get('rates', {}), 'source': 'exchangerate-api'}
        except Exception as e:
            logger.error(f"ExchangeRate-API fetch failed: {e}")
            return {'success': False, 'error': str(e)}

    def _fetch_ecb(self, base: str = 'EUR') -> Dict:
        """European Central Bank rates (EUR base, free)"""
        try:
            import urllib.request, xml.etree.ElementTree as ET
            url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
            with urllib.request.urlopen(url, timeout=10) as resp:
                content = resp.read().decode()
            root = ET.fromstring(content)
            ns = {'gesmes': 'http://www.gesmes.org/xml/2002-08-01', 'ecb': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'}
            rates = {'EUR': 1.0}
            for cube in root.findall('.//ecb:Cube[@currency]', ns):
                currency = cube.get('currency')
                rate = cube.get('rate')
                if currency and rate:
                    rates[currency] = float(rate)
            return {'success': True, 'base': 'EUR', 'rates': rates, 'source': 'ecb'}
        except Exception as e:
            logger.error(f"ECB fetch failed: {e}")
            return {'success': False, 'error': str(e)}

    def _fetch_openexchangerates(self, base: str, api_key: str = '') -> Dict:
        try:
            import urllib.request, json
            url = f"https://openexchangerates.org/api/latest.json?app_id={api_key}&base={base}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            return {'success': True, 'base': base, 'rates': data.get('rates', {}), 'source': 'openexchangerates'}
        except Exception as e:
            logger.error(f"OpenExchangeRates fetch failed: {e}")
            return {'success': False, 'error': str(e)}
