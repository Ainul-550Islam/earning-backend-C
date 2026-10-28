# api/admin_panel/currency_converter.py
"""Real-time currency conversion and exchange rate management."""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
RATES_CACHE_KEY = 'admin_panel:exchange_rates'
RATES_TTL = 3600  # 1 hour


class CurrencyConverter:
    BASE_CURRENCY = 'BDT'
    DEFAULT_RATES = {'BDT': 1.0, 'USD': 110.0, 'EUR': 120.0, 'GBP': 140.0,
                     'INR': 1.32, 'PKR': 0.38, 'MYR': 24.0}

    @classmethod
    def get_rates(cls) -> Dict[str, float]:
        cached = cache.get(RATES_CACHE_KEY)
        if cached:
            return cached
        # Try fetching from DB (admin-configured rates)
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='exchange_rates')
            rates = json.loads(obj.value)
            cache.set(RATES_CACHE_KEY, rates, RATES_TTL)
            return rates
        except Exception:
            pass
        # Try free API (exchangerate-api.com)
        try:
            import requests
            resp = requests.get(f'https://api.exchangerate-api.com/v4/latest/BDT', timeout=5)
            rates = resp.json().get('rates', cls.DEFAULT_RATES)
            cache.set(RATES_CACHE_KEY, rates, RATES_TTL)
            return rates
        except Exception:
            return cls.DEFAULT_RATES

    @classmethod
    def convert(cls, amount: float, from_currency: str, to_currency: str) -> float:
        if from_currency == to_currency:
            return amount
        rates = cls.get_rates()
        from_rate = rates.get(from_currency.upper(), 1.0)
        to_rate   = rates.get(to_currency.upper(), 1.0)
        # Convert via BDT base
        bdt_amount = amount * from_rate
        result = bdt_amount / to_rate
        return round(result, 4)

    @classmethod
    def update_rate(cls, currency: str, rate: float, actor=None) -> bool:
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            rates = cls.get_rates()
            rates[currency.upper()] = rate
            SystemConfig.objects.update_or_create(
                key='exchange_rates',
                defaults={'value': json.dumps(rates), 'group': 'finance', 'value_type': 'json'}
            )
            cache.delete(RATES_CACHE_KEY)
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='update_exchange_rate',
                                  changes={'currency': currency, 'rate': rate})
            return True
        except Exception:
            return False

    @classmethod
    def get_all_rates_display(cls) -> List[Dict]:
        rates = cls.get_rates()
        return [{'currency': k, 'rate_per_bdt': v, 'usd_equivalent': round(v/rates.get('USD',1), 4)}
                for k, v in rates.items()]

currency_converter = CurrencyConverter()