# api/cms/services.py
"""
Business logic for CMS. Move complex logic out of views.
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CMSService:
    """Service for content and notice operations."""

    @staticmethod
    def get_active_notices(limit: int = 10) -> list:
        """Return active notices for API. Override with your CMS model if you have Notice."""
        try:
            from . import models as cms_models
            if hasattr(cms_models, 'Notice'):
                return list(cms_models.Notice.objects.filter(is_active=True)[:limit])
        except Exception:
            pass
        return []
