"""
Time Targeting Service

Handles time window matching for time-based targeting
rules in offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, time as dt_time, timedelta
import pytz
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from offer_routing.models import (
    OfferRoute, TimeRouteRule, RoutingDecisionLog
)
from offer_routing.constants import (
    TIME_CACHE_TIMEOUT, TIMEZONE_CACHE_TIMEOUT,
    MAX_TIME_LOOKUPS_PER_SECOND, TIME_PARSE_TIMEOUT
)
from offer_routing.exceptions import TargetingError, TimeParsingError
from offer_routing.utils import get_user_timezone, parse_time_string

User = get_user_model()
logger = logging.getLogger(__name__)

