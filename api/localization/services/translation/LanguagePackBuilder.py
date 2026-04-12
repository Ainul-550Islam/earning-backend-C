# services/translation/LanguagePackBuilder.py
"""Language pack build pipeline — compile, minify, CDN-ready JSON"""
import hashlib
import json
import logging
from typing import Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class LanguagePackBuilder:
    """
    Language pack build service।
    Translation DB → compiled JSON → CDN-ready pack.
    Frontend এই pack lazy-load করে per namespace।
    """

    def build(
        self,
        language_code: str,
        namespace: str = 'global',
        version: str = '1.0.0',
        approved_only: bool = True,
        include_metadata: bool = True,
    ) -> Dict:
        """
        Language pack build করে।
        Returns: {'success': True, 'pack': {...}, 'meta': {...}}
        """
        try:
            from ...models.core import Language, Translation, TranslationKey

            lang = Language.objects.filter(code=language_code, is_active=True).first()
            if not lang:
                return {'success': False, 'error': f'Language {language_code} not found'}

            # Build translations dict
            qs = Translation.objects.filter(
                language=lang,
            ).select_related('key').only('key__key', 'key__category', 'value', 'is_approved')

            if approved_only:
                qs = qs.filter(is_approved=True)

            if namespace != 'global':
                qs = qs.filter(key__category=namespace)

            # Build flat dict: key → value
            translations = {}
            categories = {}
            for trans in qs:
                key = trans.key.key
                translations[key] = trans.value
                cat = trans.key.category or 'common'
                categories.setdefault(cat, 0)
                categories[cat] += 1

            # Stats
            total_keys = TranslationKey.objects.count()
            if namespace != 'global':
                total_keys = TranslationKey.objects.filter(category=namespace).count()
            translated_count = len(translations)
            coverage = round((translated_count / total_keys * 100), 2) if total_keys > 0 else 0

            # Checksum
            pack_json = json.dumps(translations, ensure_ascii=False, sort_keys=True)
            checksum = hashlib.sha256(pack_json.encode('utf-8')).hexdigest()[:16]

            pack = {
                'language': language_code,
                'namespace': namespace,
                'version': version,
                'translations': translations,
                'count': translated_count,
                'coverage': coverage,
                'checksum': checksum,
                'built_at': timezone.now().isoformat(),
            }

            if include_metadata:
                pack['meta'] = {
                    'is_rtl': lang.is_rtl,
                    'text_direction': lang.text_direction or ('rtl' if lang.is_rtl else 'ltr'),
                    'bcp47': lang.bcp47_code or language_code,
                    'font_family': lang.font_family or '',
                    'categories': categories,
                    'flag_emoji': lang.flag_emoji or '',
                }

            return {
                'success': True,
                'language': language_code,
                'namespace': namespace,
                'count': translated_count,
                'coverage': coverage,
                'checksum': checksum,
                'pack': pack,
            }

        except Exception as e:
            logger.error(f"LanguagePackBuilder.build failed for {language_code}: {e}")
            return {'success': False, 'error': str(e)}

    def build_all_namespaces(self, language_code: str) -> Dict:
        """সব namespaces-এর pack build করে"""
        try:
            from ...models.core import TranslationKey
            namespaces = list(
                TranslationKey.objects.values_list('category', flat=True)
                .distinct()
                .exclude(category='')
                .exclude(category__isnull=True)
            ) + ['global']

            results = {}
            for ns in namespaces:
                result = self.build(language_code, namespace=ns)
                results[ns] = {'success': result['success'], 'count': result.get('count', 0)}

            return {'success': True, 'language': language_code, 'namespaces': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def build_diff(
        self,
        language_code: str,
        since_version: str,
        namespace: str = 'global',
    ) -> Dict:
        """
        Incremental diff pack — only changed translations since last version.
        Frontend can merge diff with cached pack to avoid full re-download.
        """
        try:
            from ...models.core import Translation, Language
            from django.utils import timezone
            import dateutil.parser

            lang = Language.objects.filter(code=language_code, is_active=True).first()
            if not lang:
                return {'success': False, 'error': 'Language not found'}

            # Parse version as datetime (ISO format versions)
            try:
                since_dt = dateutil.parser.parse(since_version)
            except Exception:
                # Fall back to full build
                return self.build(language_code, namespace)

            qs = Translation.objects.filter(
                language=lang,
                is_approved=True,
                updated_at__gt=since_dt,
            ).select_related('key').only('key__key', 'value')

            if namespace != 'global':
                qs = qs.filter(key__category=namespace)

            changes = {t.key.key: t.value for t in qs}
            return {
                'success': True,
                'type': 'diff',
                'language': language_code,
                'since': since_version,
                'changes': changes,
                'change_count': len(changes),
                'generated_at': timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"build_diff failed: {e}")
            return self.build(language_code, namespace)

    def get_cdn_url(self, language_code: str, namespace: str, version: str) -> str:
        """Language pack CDN URL"""
        from django.conf import settings
        cdn_base = getattr(settings, 'LANGUAGE_PACK_CDN_URL', '/api/localization/public/translations')
        return f"{cdn_base}/{language_code}/{namespace}/v{version}.json"

    def get_cache_headers(self, ttl_seconds: int = 86400) -> Dict[str, str]:
        """CDN cache headers for language packs"""
        return {
            'Cache-Control': f'public, max-age={ttl_seconds}, stale-while-revalidate=3600',
            'Vary': 'Accept-Encoding',
        }
