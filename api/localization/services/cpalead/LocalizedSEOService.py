# services/cpalead/LocalizedSEOService.py
"""SEO localization — hreflang tags, locale-aware sitemap, meta tags per language."""
import logging
from typing import Dict, List
logger = logging.getLogger(__name__)


class LocalizedSEOService:
    """Handles SEO localization for CPAlead pages."""

    def generate_hreflang_tags(self, page_url: str, available_langs: List[str]) -> str:
        """hreflang HTML tags generate করে।"""
        tags = []
        for lang in available_langs:
            bcp47 = self._to_bcp47(lang)
            url = self._get_localized_url(page_url, lang)
            tags.append(f'<link rel="alternate" hreflang="{bcp47}" href="{url}">')
        # x-default: English
        tags.append(f'<link rel="alternate" hreflang="x-default" href="{page_url}">')
        return "\n".join(tags)

    def get_localized_meta(self, page_type: str, language_code: str, context: Dict) -> Dict:
        """Page-এর localized meta tags পাওয়া।"""
        try:
            from ..models.content import LocalizedSEO
            seo = LocalizedSEO.objects.filter(
                content_type=page_type,
                object_id=str(context.get("id", "")),
                language__code=language_code,
            ).first()
            if seo:
                return {
                    "title": seo.meta_title,
                    "description": seo.meta_description,
                    "og_title": seo.og_title or seo.meta_title,
                    "og_description": seo.og_description or seo.meta_description,
                    "og_image": seo.og_image_url,
                    "canonical": seo.canonical_url,
                    "is_indexable": seo.is_indexable,
                    "hreflang": seo.hreflang_tags or {},
                }
        except Exception as e:
            logger.error(f"get_localized_meta failed: {e}")
        return self._default_meta(language_code, context)

    def generate_locale_sitemap(self, base_url: str) -> str:
        """Multi-language XML sitemap generate করে।"""
        try:
            from ..models.core import Language
            langs = Language.objects.filter(is_active=True).values_list("code", flat=True)
            lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
                '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
            ]
            # Home page
            lines.append("  <url>")
            lines.append(f"    <loc>{base_url}/</loc>")
            for lang in langs:
                bcp47 = self._to_bcp47(lang)
                lines.append(f'    <xhtml:link rel="alternate" hreflang="{bcp47}" href="{base_url}/{lang}/"/>')
            lines.append("    <changefreq>daily</changefreq>")
            lines.append("    <priority>1.0</priority>")
            lines.append("  </url>")
            lines.append("</urlset>")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"generate_locale_sitemap failed: {e}")
            return ""

    def _to_bcp47(self, lang_code: str) -> str:
        BCP47_MAP = {
            "bn": "bn-BD", "en": "en-US", "zh": "zh-Hans",
            "pt": "pt-BR", "es": "es-419",
        }
        return BCP47_MAP.get(lang_code, lang_code)

    def _get_localized_url(self, base_url: str, lang_code: str) -> str:
        if lang_code == "en":
            return base_url
        return f"{base_url.rstrip('/')}/{lang_code}/"

    def _default_meta(self, language_code: str, context: Dict) -> Dict:
        return {
            "title": context.get("title", ""),
            "description": context.get("description", "")[:160],
            "is_indexable": True,
        }
