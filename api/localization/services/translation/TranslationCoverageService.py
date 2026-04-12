# services/translation/TranslationCoverageService.py
"""Translation coverage calculation — how complete is each language?"""
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
CACHE_TTL = 1800  # 30 min


class TranslationCoverageService:
    """
    Coverage = translated_keys / total_keys * 100
    Tracks per-language coverage with namespace breakdown.
    """

    def get_coverage_report(self, language_code: str = None) -> Dict:
        """
        Single language or all languages coverage report.
        language_code=None → all languages report.
        """
        if language_code:
            return self._single_language(language_code)
        return self._all_languages()

    def _single_language(self, language_code: str) -> Dict:
        """Single language coverage"""
        try:
            from ...models.core import Language, Translation, TranslationKey
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return {'error': f'Language {language_code} not found', 'language': language_code}

            total_keys = TranslationKey.objects.filter(is_active=True).count()
            if total_keys == 0:
                return {'language': language_code, 'total_keys': 0, 'translated': 0,
                        'approved': 0, 'missing': 0, 'coverage_percent': 0}

            translated = Translation.objects.filter(language=lang, value__isnull=False).exclude(value='').count()
            approved = Translation.objects.filter(language=lang, is_approved=True).exclude(value='').count()
            missing = total_keys - translated

            coverage_pct = round(Decimal(translated) / Decimal(total_keys) * 100, 2)
            approved_pct = round(Decimal(approved) / Decimal(total_keys) * 100, 2)

            # Namespace breakdown
            namespaces = {}
            from django.db.models import Count
            ns_totals = TranslationKey.objects.filter(is_active=True).values('category').annotate(count=Count('id'))
            ns_translated = Translation.objects.filter(language=lang).exclude(value='').values('key__category').annotate(count=Count('id'))
            ns_total_map = {r['category'] or 'common': r['count'] for r in ns_totals}
            ns_trans_map = {r['key__category'] or 'common': r['count'] for r in ns_translated}
            for ns, total in ns_total_map.items():
                trans = ns_trans_map.get(ns, 0)
                namespaces[ns] = {
                    'total': total,
                    'translated': trans,
                    'percent': round(trans / total * 100, 1) if total > 0 else 0,
                }

            return {
                'language': language_code,
                'language_name': lang.name,
                'flag': lang.flag_emoji or '',
                'total_keys': total_keys,
                'translated': translated,
                'approved': approved,
                'missing': missing,
                'coverage_percent': float(coverage_pct),
                'approved_percent': float(approved_pct),
                'namespaces': namespaces,
                'is_rtl': lang.is_rtl,
                'calculated_at': timezone.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Coverage for {language_code} failed: {e}")
            return {'error': str(e), 'language': language_code}

    def _all_languages(self) -> Dict:
        """All languages combined report"""
        try:
            from ...models.core import Language
            results = []
            for lang in Language.objects.filter(is_active=True).order_by('-is_default', 'name'):
                report = self._single_language(lang.code)
                results.append(report)
            return {'languages': results, 'total_languages': len(results)}
        except Exception as e:
            logger.error(f"All-language coverage failed: {e}")
            return {'error': str(e), 'languages': []}

    def calculate_all(self) -> List[Dict]:
        """All languages list — used by Celery task and admin"""
        try:
            from ...models.core import Language
            results = []
            for lang in Language.objects.filter(is_active=True):
                report = self._single_language(lang.code)
                if 'error' not in report:
                    results.append({'language': lang.code, **report})
                    # Save to TranslationCoverage model
                    self._save_coverage(lang, report)
            return results
        except Exception as e:
            logger.error(f"calculate_all failed: {e}")
            return []

    def _save_coverage(self, lang, report: Dict):
        """Coverage results DB-তে save করে"""
        try:
            from ...models.analytics import TranslationCoverage
            TranslationCoverage.objects.update_or_create(
                language=lang,
                defaults={
                    'total_keys': report.get('total_keys', 0),
                    'translated_keys': report.get('translated', 0),
                    'approved_keys': report.get('approved', 0),
                    'coverage_percent': report.get('coverage_percent', 0),
                    'approved_percent': report.get('approved_percent', 0),
                    'missing_keys': report.get('missing', 0),
                    'last_calculated_at': timezone.now(),
                }
            )
        except Exception as e:
            logger.debug(f"Coverage save failed: {e}")
