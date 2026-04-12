"""
api/ai_engine/ML_MODELS/feature_engineering.py
===============================================
Feature Engineering — raw data থেকে ML features তৈরি।
"""

import logging
import math
from typing import Dict, Any, List, Optional
from datetime import timedelta
from django.utils import timezone
from ..utils import days_since, hours_since, safe_ratio

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Feature type অনুযায়ী features extract করো।
    """

    def __init__(self, feature_type: str = 'general'):
        self.feature_type = feature_type

    def extract(self, raw_data: dict) -> dict:
        """Raw data থেকে ML-ready features তৈরি করো।"""
        extractors = {
            'fraud':        self._fraud_features,
            'churn':        self._churn_features,
            'ltv':          self._ltv_features,
            'behavioral':   self._behavioral_features,
            'recommendation': self._recommendation_features,
            'general':      self._general_features,
        }
        fn = extractors.get(self.feature_type, self._general_features)
        return fn(raw_data)

    def _fraud_features(self, data: dict) -> dict:
        return {
            'is_vpn':           int(data.get('is_vpn', False)),
            'is_proxy':         int(data.get('is_proxy', False)),
            'is_tor':           int(data.get('is_tor', False)),
            'device_count':     min(data.get('device_count', 1), 10),
            'account_age_days': min(data.get('account_age_days', 0), 365),
            'click_rate_1h':    min(data.get('click_rate_1h', 0), 200),
            'ip_risk_score':    float(data.get('ip_risk_score', 0.0)),
            'country_risk':     float(data.get('country_risk', 0.0)),
            'same_ip_accounts': min(data.get('same_ip_accounts', 0), 20),
        }

    def _churn_features(self, data: dict) -> dict:
        return {
            'days_since_login':    min(data.get('days_since_login', 0), 90),
            'days_since_earn':     min(data.get('days_since_earn', 0), 90),
            'total_earned':        min(float(data.get('total_earned', 0)), 100000),
            'coin_balance':        min(float(data.get('coin_balance', 0)), 100000),
            'streak_count':        min(data.get('streak_count', 0), 365),
            'referral_count':      min(data.get('referral_count', 0), 100),
            'offers_completed':    min(data.get('offers_completed', 0), 500),
            'avg_session_minutes': min(data.get('avg_session_minutes', 0), 120),
        }

    def _ltv_features(self, data: dict) -> dict:
        return {
            'account_age_days':    data.get('account_age_days', 0),
            'total_earned':        float(data.get('total_earned', 0)),
            'referral_count':      data.get('referral_count', 0),
            'offers_completed':    data.get('offers_completed', 0),
            'avg_daily_earn':      float(data.get('avg_daily_earn', 0)),
            'country_avg_revenue': float(data.get('country_avg_revenue', 0)),
        }

    def _behavioral_features(self, data: dict) -> dict:
        return {
            'session_count_7d':    data.get('session_count_7d', 0),
            'clicks_7d':           data.get('clicks_7d', 0),
            'conversions_7d':      data.get('conversions_7d', 0),
            'avg_session_time':    data.get('avg_session_time', 0),
            'preferred_time_hour': data.get('preferred_time_hour', 12),
            'is_mobile':           int(data.get('is_mobile', True)),
            'notification_clicks': data.get('notification_clicks', 0),
        }

    def _recommendation_features(self, data: dict) -> dict:
        return {
            'user_id':          data.get('user_id', ''),
            'category_pref':    data.get('category_pref', []),
            'reward_type_pref': data.get('reward_type_pref', []),
            'difficulty_pref':  data.get('difficulty_pref', 'medium'),
            'country':          data.get('country', 'BD'),
            'device':           data.get('device', 'mobile'),
        }

    def _general_features(self, data: dict) -> dict:
        """Pass-through with basic sanitization।"""
        result = {}
        for k, v in data.items():
            if isinstance(v, (int, float, bool, str)):
                result[k] = v
        return result
