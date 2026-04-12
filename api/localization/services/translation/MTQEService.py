# services/translation/MTQEService.py
"""
Machine Translation Quality Estimation (MTQE).
Estimates quality of machine-translated text without human reference.
Scoring: 0-100. >85 = publish, 70-85 = review, <70 = retranslate.
"""
import re
import logging
from typing import Dict
logger = logging.getLogger(__name__)


class MTQEService:
    """
    Machine translation quality estimation using heuristics.
    Real MTQE systems use ML models (COMET, etc.) — this is a solid heuristic baseline.
    """

    def estimate(self, source: str, translated: str, source_lang: str, target_lang: str) -> Dict:
        """
        Translation quality estimate করে।
        Returns score 0-100 with breakdown.
        """
        if not source or not translated:
            return {'score': 0, 'label': 'empty', 'issues': ['Empty text']}

        scores = {}
        issues = []

        # 1. Length ratio check (50% weight)
        scores['length'] = self._check_length_ratio(source, translated, source_lang, target_lang)
        if scores['length'] < 50:
            issues.append(f"Unusual length ratio ({len(translated)}/{len(source)} chars)")

        # 2. Placeholder preservation (20% weight)
        scores['placeholders'] = self._check_placeholders(source, translated)
        if scores['placeholders'] < 100:
            issues.append("Placeholder mismatch detected")

        # 3. Punctuation preservation (10% weight)
        scores['punctuation'] = self._check_punctuation(source, translated)
        if scores['punctuation'] < 70:
            issues.append("Punctuation pattern changed significantly")

        # 4. Untranslated detection (10% weight)
        scores['untranslated'] = self._check_not_copied(source, translated, source_lang, target_lang)
        if scores['untranslated'] < 80:
            issues.append("Text may be untranslated (too similar to source)")

        # 5. Character script check (10% weight)
        scores['script'] = self._check_script(translated, target_lang)
        if scores['script'] < 80:
            issues.append(f"Script mismatch for {target_lang}")

        # Weighted score
        total = (
            scores['length'] * 0.35 +
            scores['placeholders'] * 0.25 +
            scores['punctuation'] * 0.15 +
            scores['untranslated'] * 0.15 +
            scores['script'] * 0.10
        )
        total = round(total, 1)

        label = 'excellent' if total >= 90 else ('good' if total >= 75 else ('needs_review' if total >= 60 else 'poor'))

        return {
            'score': total,
            'label': label,
            'breakdown': scores,
            'issues': issues,
            'recommendation': self._recommendation(total),
            'source_lang': source_lang,
            'target_lang': target_lang,
        }

    def _check_length_ratio(self, source: str, translated: str, src_lang: str, tgt_lang: str) -> float:
        """Length ratio check — CJK languages expect shorter output."""
        src_len = len(source)
        tgt_len = len(translated)
        if src_len == 0:
            return 0
        ratio = tgt_len / src_len
        # CJK langs pack more meaning per char
        cjk = {'zh', 'ja', 'ko'}
        if tgt_lang in cjk:
            ok = 0.3 <= ratio <= 1.2
        elif src_lang in cjk:
            ok = 1.0 <= ratio <= 4.0
        else:
            ok = 0.5 <= ratio <= 2.5

        if ok:
            return 100.0
        deviation = abs(ratio - 1.0)
        return max(0, round(100 - deviation * 40, 1))

    def _check_placeholders(self, source: str, translated: str) -> float:
        """All placeholders in source must appear in translated."""
        patterns = [r'\{[^}]+\}', r'%[sdif]', r'%\([^)]+\)s', r'{{[^}]+}}', r'<[a-zA-Z][^>]*>']
        src_phs = set()
        tgt_phs = set()
        for p in patterns:
            src_phs.update(re.findall(p, source))
            tgt_phs.update(re.findall(p, translated))
        if not src_phs:
            return 100.0
        missing = src_phs - tgt_phs
        extra = tgt_phs - src_phs
        penalty = (len(missing) + len(extra)) * 25
        return max(0, 100 - penalty)

    def _check_punctuation(self, source: str, translated: str) -> float:
        """Sentence-ending punctuation should match approximately."""
        src_endings = re.findall(r'[.!?।۔。！？]', source)
        tgt_endings = re.findall(r'[.!?।۔。！？]', translated)
        if not src_endings:
            return 100.0
        diff = abs(len(src_endings) - len(tgt_endings))
        return max(0, round(100 - diff * 20, 1))

    def _check_not_copied(self, source: str, translated: str, src_lang: str, tgt_lang: str) -> float:
        """Check translation isn't just a copy of source (for non-similar-script langs)."""
        if src_lang == tgt_lang:
            return 100.0
        # Different scripts — source and target should differ significantly
        from ..utils.fuzzy import levenshtein_similarity
        similarity = levenshtein_similarity(source, translated)
        if similarity > 85:  # Too similar — likely untranslated
            return max(0, round(100 - similarity, 1))
        return 100.0

    def _check_script(self, translated: str, target_lang: str) -> float:
        """Check that translated text uses the expected script."""
        SCRIPT_RANGES = {
            'ar': r'[\u0600-\u06FF]', 'he': r'[\u0590-\u05FF]',
            'ur': r'[\u0600-\u06FF]', 'fa': r'[\u0600-\u06FF]',
            'bn': r'[\u0980-\u09FF]', 'hi': r'[\u0900-\u097F]',
            'ta': r'[\u0B80-\u0BFF]', 'te': r'[\u0C00-\u0C7F]',
            'zh': r'[\u4E00-\u9FFF]', 'ja': r'[\u3040-\u30FF\u4E00-\u9FFF]',
            'ko': r'[\uAC00-\uD7AF]', 'my': r'[\u1000-\u109F]',
            'si': r'[\u0D80-\u0DFF]', 'ne': r'[\u0900-\u097F]',
            'km': r'[\u1780-\u17FF]', 'th': r'[\u0E00-\u0E7F]',
        }
        pattern = SCRIPT_RANGES.get(target_lang)
        if not pattern:
            return 100.0  # Latin or unknown — skip check
        matches = len(re.findall(pattern, translated))
        total_alpha = len(re.findall(r'\S', translated))
        if total_alpha == 0:
            return 100.0
        ratio = matches / total_alpha
        return round(min(100, ratio * 150), 1)  # Expect 65%+ target script chars

    def _recommendation(self, score: float) -> str:
        if score >= 90:
            return 'auto_approve'
        if score >= 75:
            return 'review_then_approve'
        if score >= 60:
            return 'professional_review'
        return 'retranslate'

    def batch_estimate(self, pairs: list, source_lang: str, target_lang: str) -> list:
        """Multiple pairs-এর quality estimate করে।"""
        return [
            self.estimate(src, tgt, source_lang, target_lang)
            for src, tgt in pairs
        ]
