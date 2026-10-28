"""
Device Targeting Service

Handles user agent parsing and device matching for
device-based targeting rules in offer routing system.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from offer_routing.models import (
    OfferRoute, DeviceRouteRule, RoutingDecisionLog
)
from offer_routing.choices import DeviceType, OSType, BrowserType
from offer_routing.constants import (
    DEVICE_CACHE_TIMEOUT, USER_AGENT_CACHE_TIMEOUT,
    MAX_DEVICE_LOOKUPS_PER_SECOND, DEVICE_PARSE_TIMEOUT
)
from offer_routing.exceptions import TargetingError, DeviceParsingError
from offer_routing.utils import parse_user_agent, extract_device_info

User = get_user_model()
logger = logging.getLogger(__name__)

