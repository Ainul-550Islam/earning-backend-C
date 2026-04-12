# =============================================================================
# api/promotions/localization/timezone_manager.py
# Timezone Manager — User এর local time অনুযায়ী scheduling ও display
# =============================================================================

import logging
from datetime import datetime, timezone as dt_tz
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.cache import cache

logger = logging.getLogger('localization.timezone')
CACHE_PREFIX_TZ = 'loc:tz:{}'

# Country → Primary timezone mapping
COUNTRY_TIMEZONES = {
    'BD': 'Asia/Dhaka',          # Bangladesh UTC+6
    'IN': 'Asia/Kolkata',        # India UTC+5:30
    'PK': 'Asia/Karachi',        # Pakistan UTC+5
    'LK': 'Asia/Colombo',        # Sri Lanka UTC+5:30
    'NP': 'Asia/Kathmandu',      # Nepal UTC+5:45
    'ID': 'Asia/Jakarta',        # Indonesia UTC+7
    'PH': 'Asia/Manila',         # Philippines UTC+8
    'MY': 'Asia/Kuala_Lumpur',   # Malaysia UTC+8
    'SG': 'Asia/Singapore',      # Singapore UTC+8
    'TH': 'Asia/Bangkok',        # Thailand UTC+7
    'VN': 'Asia/Ho_Chi_Minh',    # Vietnam UTC+7
    'MM': 'Asia/Rangoon',        # Myanmar UTC+6:30
    'KH': 'Asia/Phnom_Penh',     # Cambodia UTC+7
    'NG': 'Africa/Lagos',        # Nigeria UTC+1
    'GH': 'Africa/Accra',        # Ghana UTC+0
    'KE': 'Africa/Nairobi',      # Kenya UTC+3
    'EG': 'Africa/Cairo',        # Egypt UTC+2
    'ZA': 'Africa/Johannesburg', # South Africa UTC+2
    'BR': 'America/Sao_Paulo',
    'MX': 'America/Mexico_City',
    'CO': 'America/Bogota',
    'AR': 'America/Argentina/Buenos_Aires',
    'PE': 'America/Lima',
    'US': 'America/New_York',    # Default to EST
    'CA': 'America/Toronto',
    'GB': 'Europe/London',
    'DE': 'Europe/Berlin',
    'FR': 'Europe/Paris',
    'TR': 'Europe/Istanbul',
    'RU': 'Europe/Moscow',
    'SA': 'Asia/Riyadh',
    'AE': 'Asia/Dubai',
    'JP': 'Asia/Tokyo',
    'KR': 'Asia/Seoul',
    'CN': 'Asia/Shanghai',
    'AU': 'Australia/Sydney',
    'NZ': 'Pacific/Auckland',
}


class TimezoneManager:
    """
    User timezone management।

    Features:
    1. Country/IP থেকে timezone detect
    2. UTC ↔ Local time conversion
    3. Campaign scheduling local time এ
    4. Task deadline local time এ display
    5. Working hours check (যেমন আফ্রিকায় রাত ৩টায় campaign না চালানো)
    """

    def get_timezone(self, country: str = None, user_tz: str = None) -> ZoneInfo:
        """User এর timezone return করে।"""
        # User প্রদত্ত timezone
        if user_tz:
            try:
                return ZoneInfo(user_tz)
            except ZoneInfoNotFoundError:
                pass

        # Country-based
        if country:
            tz_name = COUNTRY_TIMEZONES.get(country.upper(), 'UTC')
            try:
                return ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                pass

        return ZoneInfo('UTC')

    def to_local(self, utc_dt: datetime, country: str = None, user_tz: str = None) -> datetime:
        """UTC datetime কে local time এ convert করে।"""
        tz = self.get_timezone(country, user_tz)
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=dt_tz.utc)
        return utc_dt.astimezone(tz)

    def to_utc(self, local_dt: datetime, country: str = None, user_tz: str = None) -> datetime:
        """Local datetime কে UTC তে convert করে।"""
        tz = self.get_timezone(country, user_tz)
        if local_dt.tzinfo is None:
            local_dt = local_dt.replace(tzinfo=tz)
        return local_dt.astimezone(dt_tz.utc)

    def get_local_time_now(self, country: str = None, user_tz: str = None) -> datetime:
        """এখনকার local time return করে।"""
        from django.utils import timezone
        return self.to_local(timezone.now(), country, user_tz)

    def is_working_hours(self, country: str, hour: int = None) -> bool:
        """Country তে working hours কিনা check করে (campaign scheduling)।"""
        if hour is None:
            local_now = self.get_local_time_now(country)
            hour      = local_now.hour
        # 8:00 - 22:00 = working hours
        return 8 <= hour < 22

    def format_datetime_local(
        self, utc_dt: datetime, country: str, fmt: str = '%Y-%m-%d %H:%M'
    ) -> str:
        """UTC datetime কে local formatted string এ convert করে।"""
        local = self.to_local(utc_dt, country)
        return local.strftime(fmt)

    def get_campaign_schedule_times(
        self, utc_start: datetime, utc_end: datetime, country: str
    ) -> dict:
        """Campaign schedule UTC time কে local time এ convert করে।"""
        return {
            'start_local': self.format_datetime_local(utc_start, country),
            'end_local':   self.format_datetime_local(utc_end, country),
            'timezone':    COUNTRY_TIMEZONES.get(country.upper(), 'UTC'),
        }

    def get_all_country_timezones(self) -> dict:
        return {k: v for k, v in COUNTRY_TIMEZONES.items()}
