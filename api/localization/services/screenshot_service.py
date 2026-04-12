# services/screenshot_service.py
"""
Screenshot/Visual Context Service — translators দেখতে পায় key কোথায় ব্যবহার হয়।
Phrase.com screenshot feature equivalent।
"""
import base64
import hashlib
import logging
from typing import Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class ScreenshotService:
    """
    Translation key-এর visual context manage করে।
    Features:
    - Upload screenshot (base64 or URL)
    - Link screenshot to translation key(s)
    - Get all screenshots for a key
    - Auto-tag from page URL
    """

    def upload_screenshot(
        self,
        image_data: str = None,
        image_url: str = None,
        page_url: str = '',
        title: str = '',
        component: str = '',
        key_names: List[str] = None,
        uploaded_by=None,
        region: Dict = None,
    ) -> Dict:
        """
        Screenshot upload করে এবং translation keys-এর সাথে link করে।

        image_data: base64 encoded image string
        image_url: CDN URL (if already uploaded externally)
        key_names: list of translation key strings to link ['offer.title', 'offer.complete']
        region: {'x': 10, 'y': 20, 'w': 200, 'h': 50} — highlight region in screenshot
        """
        try:
            from ..models.content import TranslationScreenshot
            from ..models.core import TranslationKey

            # Validate: need either image_data or image_url
            if not image_data and not image_url:
                return {'success': False, 'error': 'image_data or image_url required'}

            # Auto-generate title from page_url if not given
            if not title and page_url:
                title = self._title_from_url(page_url)

            # Compress base64 if large
            if image_data and len(image_data) > 500_000:
                image_data = self._compress_base64(image_data)

            # Create screenshot
            screenshot = TranslationScreenshot.objects.create(
                title=title,
                image_url=image_url or '',
                image_data=image_data or '',
                page_url=page_url,
                component=component,
                uploaded_by=uploaded_by,
                region_x=region.get('x') if region else None,
                region_y=region.get('y') if region else None,
                region_w=region.get('w') if region else None,
                region_h=region.get('h') if region else None,
                tags=self._auto_tags(page_url, component),
            )

            # Link to translation keys
            linked_keys = []
            if key_names:
                for key_name in key_names:
                    tkey = TranslationKey.objects.filter(key=key_name).first()
                    if tkey:
                        screenshot.translation_key = tkey
                        screenshot.save(update_fields=['translation_key'])
                        linked_keys.append(key_name)

            return {
                'success': True,
                'screenshot_id': screenshot.pk,
                'title': screenshot.title,
                'page_url': page_url,
                'linked_keys': linked_keys,
            }

        except Exception as e:
            logger.error(f"Screenshot upload failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_for_key(self, key_name: str) -> List[Dict]:
        """Translation key-এর সব screenshots পাওয়া"""
        try:
            from ..models.content import TranslationScreenshot
            shots = TranslationScreenshot.objects.filter(
                translation_key__key=key_name
            ).order_by('-created_at')

            return [
                {
                    'id': s.pk,
                    'title': s.title,
                    'image_url': s.image_url,
                    'has_image_data': bool(s.image_data),
                    'page_url': s.page_url,
                    'component': s.component,
                    'region': {
                        'x': s.region_x, 'y': s.region_y,
                        'w': s.region_w, 'h': s.region_h,
                    } if s.region_x is not None else None,
                    'tags': s.tags,
                    'uploaded_at': s.created_at.isoformat() if s.created_at else None,
                }
                for s in shots
            ]
        except Exception as e:
            logger.error(f"get_for_key failed: {e}")
            return []

    def get_image_data(self, screenshot_id: int) -> Optional[str]:
        """Screenshot base64 image data পাওয়া"""
        try:
            from ..models.content import TranslationScreenshot
            s = TranslationScreenshot.objects.filter(pk=screenshot_id).first()
            return s.image_data if s else None
        except Exception:
            return None

    def bulk_link_keys(self, screenshot_id: int, key_names: List[str]) -> Dict:
        """Existing screenshot-কে multiple keys-এর সাথে link করে"""
        try:
            from ..models.content import TranslationScreenshot
            from ..models.core import TranslationKey
            shot = TranslationScreenshot.objects.filter(pk=screenshot_id).first()
            if not shot:
                return {'success': False, 'error': 'Screenshot not found'}

            linked = []
            for key_name in key_names:
                tkey = TranslationKey.objects.filter(key=key_name).first()
                if tkey:
                    # Create a copy linked to each additional key
                    if not shot.translation_key:
                        shot.translation_key = tkey
                        shot.save(update_fields=['translation_key'])
                    else:
                        TranslationScreenshot.objects.create(
                            translation_key=tkey,
                            title=shot.title,
                            image_url=shot.image_url,
                            image_data=shot.image_data,
                            page_url=shot.page_url,
                            component=shot.component,
                        )
                    linked.append(key_name)

            return {'success': True, 'linked': linked}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_screenshot(self, screenshot_id: int) -> bool:
        try:
            from ..models.content import TranslationScreenshot
            TranslationScreenshot.objects.filter(pk=screenshot_id).delete()
            return True
        except Exception:
            return False

    def get_keys_without_screenshots(self, limit: int = 100) -> List[str]:
        """Screenshot নেই এমন important keys"""
        try:
            from ..models.core import TranslationKey
            from ..models.content import TranslationScreenshot
            linked_key_ids = TranslationScreenshot.objects.values_list('translation_key_id', flat=True).distinct()
            keys = TranslationKey.objects.filter(
                is_active=True
            ).exclude(
                pk__in=linked_key_ids
            ).order_by('category', 'key')[:limit]
            return [k.key for k in keys]
        except Exception:
            return []

    def _title_from_url(self, url: str) -> str:
        """URL থেকে readable title generate করে"""
        try:
            from urllib.parse import urlparse
            path = urlparse(url).path.strip('/')
            parts = [p.replace('-', ' ').replace('_', ' ').title() for p in path.split('/') if p]
            return ' / '.join(parts) or url
        except Exception:
            return url

    def _compress_base64(self, image_data: str) -> str:
        """Large base64 images strip করে (header only for reference)"""
        # Keep first 5000 chars as preview if image is too large
        return image_data[:5000] + '...[truncated]'

    def _auto_tags(self, page_url: str, component: str) -> List[str]:
        """Auto-generate tags from URL and component name"""
        tags = []
        if page_url:
            if '/offer' in page_url:
                tags.append('offers')
            if '/dashboard' in page_url:
                tags.append('dashboard')
            if '/auth' in page_url or '/login' in page_url:
                tags.append('auth')
            if '/withdraw' in page_url:
                tags.append('withdraw')
        if component:
            tags.append(component.lower())
        return list(set(tags))
