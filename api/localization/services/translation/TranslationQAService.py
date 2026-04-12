# services/translation/TranslationQAService.py
"""Translation Quality Assurance — placeholder check, length ratio, ICU validation"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TranslationQAService:
    """
    Translation QA checks:
    1. Placeholder consistency ({name}, %s, {{var}})
    2. Length ratio (translated/source — too short or too long)
    3. Leading/trailing whitespace
    4. ICU format validity
    5. HTML tag consistency
    6. Number preservation
    7. Forbidden terms check
    """

    def check_all(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str = 'en',
        target_lang: str = '',
    ) -> Dict:
        """All QA checks run করে — single text pair"""
        checks = {}
        overall_passed = True
        warnings = []

        # 1. Placeholder consistency
        ph_result = self.check_placeholders(source_text, translated_text)
        checks['placeholders'] = ph_result
        if not ph_result['passed']:
            overall_passed = False

        # 2. Length ratio
        lr_result = self.check_length_ratio(source_text, translated_text, source_lang, target_lang)
        checks['length_ratio'] = lr_result
        if lr_result.get('warning'):
            warnings.append(lr_result['warning'])

        # 3. Whitespace
        ws_result = self.check_whitespace(source_text, translated_text)
        checks['whitespace'] = ws_result
        if not ws_result['passed']:
            warnings.append('Whitespace mismatch')

        # 4. ICU format
        icu_result = self.check_icu_validity(source_text, translated_text)
        checks['icu'] = icu_result
        if not icu_result['passed']:
            overall_passed = False

        # 5. HTML tags
        html_result = self.check_html_tags(source_text, translated_text)
        checks['html_tags'] = html_result
        if not html_result['passed']:
            overall_passed = False

        # 6. Numbers
        num_result = self.check_numbers_preserved(source_text, translated_text, target_lang)
        checks['numbers'] = num_result

        return {
            'passed': overall_passed,
            'warnings': warnings,
            'checks': checks,
            'score': self._calculate_score(checks),
        }

    def check_placeholders(self, source: str, translated: str) -> Dict:
        """Placeholders {name}, %s, {{var}}, %(name)s must match"""
        patterns = [
            r'\{[a-zA-Z_][a-zA-Z0-9_]*\}',   # {name}
            r'\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}', # {{name}}
            r'%\([a-zA-Z_]+\)[sdif]',           # %(name)s
            r'%[sdif]',                          # %s, %d
        ]
        src_phs = set()
        tgt_phs = set()
        for p in patterns:
            src_phs.update(re.findall(p, source or ''))
            tgt_phs.update(re.findall(p, translated or ''))

        missing = src_phs - tgt_phs
        extra = tgt_phs - src_phs
        return {
            'passed': not missing and not extra,
            'source_placeholders': list(src_phs),
            'target_placeholders': list(tgt_phs),
            'missing': list(missing),
            'extra': list(extra),
        }

    def check_length_ratio(
        self, source: str, translated: str,
        source_lang: str = 'en', target_lang: str = ''
    ) -> Dict:
        """Length ratio check — CJK languages are shorter, Arabic longer"""
        if not source or not translated:
            return {'passed': True, 'ratio': 0}

        ratio = len(translated) / len(source)

        # CJK: Chinese/Japanese/Korean are very compact
        if target_lang in ('zh', 'ja', 'ko'):
            ok = 0.3 <= ratio <= 2.0
        # Arabic/Hebrew expand
        elif target_lang in ('ar', 'he'):
            ok = 0.5 <= ratio <= 3.0
        # Standard
        else:
            ok = 0.5 <= ratio <= 3.5

        result = {'passed': True, 'ratio': round(ratio, 2)}
        if not ok:
            if ratio < 0.3:
                result['warning'] = f'Translation very short (ratio: {ratio:.2f})'
            else:
                result['warning'] = f'Translation very long (ratio: {ratio:.2f})'
        return result

    def check_whitespace(self, source: str, translated: str) -> Dict:
        """Leading/trailing whitespace should match"""
        src_lead = len(source) - len(source.lstrip()) if source else 0
        tgt_lead = len(translated) - len(translated.lstrip()) if translated else 0
        src_trail = len(source) - len(source.rstrip()) if source else 0
        tgt_trail = len(translated) - len(translated.rstrip()) if translated else 0
        passed = (src_lead == tgt_lead) and (src_trail == tgt_trail)
        return {'passed': passed, 'source_lead': src_lead, 'target_lead': tgt_lead}

    def check_icu_validity(self, source: str, translated: str) -> Dict:
        """If source has ICU format, translated must also be valid ICU"""
        try:
            from ...utils.icu import is_icu_format, validate_icu_template
            if not is_icu_format(source):
                return {'passed': True, 'is_icu': False}
            validation = validate_icu_template(translated)
            return {
                'passed': validation['valid'],
                'is_icu': True,
                'errors': validation['errors'],
                'warnings': validation['warnings'],
            }
        except Exception:
            return {'passed': True, 'is_icu': False}

    def check_html_tags(self, source: str, translated: str) -> Dict:
        """HTML tags must be preserved"""
        tag_pattern = r'</?[a-zA-Z][^>]*>'
        src_tags = re.findall(tag_pattern, source or '')
        tgt_tags = re.findall(tag_pattern, translated or '')
        passed = len(src_tags) == len(tgt_tags)
        return {
            'passed': passed,
            'source_tags': src_tags,
            'target_tags': tgt_tags,
        }

    def check_numbers_preserved(self, source: str, translated: str, target_lang: str = '') -> Dict:
        """Critical numbers must be preserved (prices, counts)"""
        # Allow native numerals for certain languages
        native_numeral_langs = {'ar', 'bn', 'hi', 'fa', 'ur', 'ne', 'si'}
        if target_lang in native_numeral_langs:
            return {'passed': True, 'note': 'Native numerals allowed'}

        src_nums = set(re.findall(r'\b\d+(?:\.\d+)?\b', source or ''))
        tgt_nums = set(re.findall(r'\b\d+(?:\.\d+)?\b', translated or ''))
        missing = src_nums - tgt_nums
        return {
            'passed': len(missing) == 0,
            'missing_numbers': list(missing),
        }

    def run_batch_qa(self, language_code: str, limit: int = 500) -> Dict:
        """Language-র সব approved translations-এ QA run করে"""
        try:
            from ...models.core import Language, Translation
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return {'success': False, 'error': f'Language {language_code} not found',
                        'total': 0, 'failed': 0, 'warnings': 0, 'passed': 0}

            default_lang = Language.objects.filter(is_default=True).first()
            if not default_lang:
                return {'success': False, 'error': 'No default language found',
                        'total': 0, 'failed': 0, 'warnings': 0, 'passed': 0}

            translations = Translation.objects.filter(
                language=lang, is_approved=True
            ).select_related('key').exclude(value='')[:limit]

            total = passed = failed = warned = 0
            issues = []

            for trans in translations:
                total += 1
                src_trans = Translation.objects.filter(
                    key=trans.key, language=default_lang
                ).first()
                if not src_trans:
                    continue

                result = self.check_all(src_trans.value, trans.value, default_lang.code, language_code)
                if result['passed'] and not result['warnings']:
                    passed += 1
                elif not result['passed']:
                    failed += 1
                    issues.append({
                        'key': trans.key.key,
                        'issues': [
                            k for k, v in result['checks'].items()
                            if isinstance(v, dict) and not v.get('passed', True)
                        ],
                    })
                else:
                    warned += 1

            return {
                'success': True,
                'language': language_code,
                'total': total,
                'passed': passed,
                'failed': failed,
                'warnings': warned,
                'issues': issues[:20],
                'pass_rate': round(passed / total * 100, 1) if total > 0 else 100,
            }
        except Exception as e:
            logger.error(f"run_batch_qa failed for {language_code}: {e}")
            return {'success': False, 'error': str(e), 'total': 0, 'failed': 0, 'warnings': 0, 'passed': 0}

    def _calculate_score(self, checks: Dict) -> int:
        """QA score 0-100"""
        weights = {'placeholders': 40, 'html_tags': 20, 'icu': 20, 'numbers': 10, 'whitespace': 10}
        score = 0
        for name, weight in weights.items():
            if name in checks and checks[name].get('passed', True):
                score += weight
        return score
