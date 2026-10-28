"""
User Segment Targeting Service

Handles user segment evaluation for tier/new/active/churned
user segment targeting rules in offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.cache import cache