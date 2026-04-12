# services/translation/LQAService.py
"""
LQA — Linguistic Quality Assurance metrics.
Industry-standard MQM (Multidimensional Quality Metrics) scoring.
"""
import re
import logging
from typing import Dict, List, Tuple
logger = logging.getLogger(__name__)

# MQM Error categories and their severity weights
MQM_CATEGORIES = {
    "accuracy":        {"weight": 10, "types": ["mistranslation", "omission", "addition", "untranslated"]},
    "fluency":         {"weight": 7,  "types": ["grammar", "spelling", "punctuation", "register"]},
    "terminology":     {"weight": 8,  "types": ["inconsistent_term", "wrong_term", "forbidden_term"]},
    "style":           {"weight": 4,  "types": ["awkward_phrasing", "wrong_register", "inconsistency"]},
    "locale_convention":{"weight": 6, "types": ["date_format", "number_format", "currency_format"]},
    "verity":          {"weight": 9,  "types": ["real_world_error", "factual_error"]},
}


class LQAService:
    """Language Quality Assurance — MQM-based scoring."""

    def evaluate(
        self,
        source: str,
        translated: str,
        source_lang: str,
        target_lang: str,
        word_count: int = None,
    ) -> Dict:
        """
        Full LQA evaluation — returns MQM score + issue breakdown.
        Score: 0 errors = 100%, each weighted error deducts from 100.
        """
        if not source or not translated:
            return {"lqa_score": 0, "grade": "F", "issues": ["Empty text"]}

        if word_count is None:
            word_count = max(len(source.split()), 1)

        issues = []
        total_penalty = 0.0

        # 1. Accuracy checks
        acc_issues = self._check_accuracy(source, translated, source_lang, target_lang)
        issues.extend(acc_issues)
        for iss in acc_issues:
            total_penalty += MQM_CATEGORIES["accuracy"]["weight"] * (2 if iss["severity"] == "critical" else 1)

        # 2. Fluency checks
        flu_issues = self._check_fluency(translated, target_lang)
        issues.extend(flu_issues)
        for iss in flu_issues:
            total_penalty += MQM_CATEGORIES["fluency"]["weight"] * (2 if iss["severity"] == "critical" else 0.5)

        # 3. Locale convention checks
        loc_issues = self._check_locale_conventions(translated, target_lang)
        issues.extend(loc_issues)
        for iss in loc_issues:
            total_penalty += MQM_CATEGORIES["locale_convention"]["weight"] * 0.5

        # Normalize: MQM score per word
        errors_per_word = total_penalty / word_count if word_count > 0 else 0
        lqa_score = max(0, round(100 - errors_per_word * 10, 1))

        grade = (
            "A" if lqa_score >= 95 else
            "B" if lqa_score >= 85 else
            "C" if lqa_score >= 70 else
            "D" if lqa_score >= 55 else "F"
        )

        return {
            "lqa_score": lqa_score,
            "grade": grade,
            "errors_per_word": round(errors_per_word, 3),
            "total_penalty": total_penalty,
            "word_count": word_count,
            "issue_count": len(issues),
            "issues": issues,
            "recommendation": "approve" if lqa_score >= 85 else ("review" if lqa_score >= 60 else "retranslate"),
        }

    def _check_accuracy(self, source: str, translated: str, src_lang: str, tgt_lang: str) -> List[Dict]:
        issues = []
        # Placeholder mismatch
        ph_pattern = re.compile(r'\{[^}]+\}|%[sdif]|{{[^}]+}}')
        src_phs = set(ph_pattern.findall(source))
        tgt_phs = set(ph_pattern.findall(translated))
        for missing in src_phs - tgt_phs:
            issues.append({"category": "accuracy", "type": "omission", "severity": "critical",
                           "text": f"Missing placeholder: {missing}"})
        for extra in tgt_phs - src_phs:
            issues.append({"category": "accuracy", "type": "addition", "severity": "major",
                           "text": f"Extra placeholder: {extra}"})
        # Untranslated check (for non-similar scripts)
        if src_lang != tgt_lang and len(translated) > 5:
            from ..utils.fuzzy import levenshtein_similarity
            sim = levenshtein_similarity(source, translated)
            if sim > 90:
                issues.append({"category": "accuracy", "type": "untranslated", "severity": "critical",
                               "text": "Text appears to be untranslated (too similar to source)"})
        return issues

    def _check_fluency(self, text: str, lang: str) -> List[Dict]:
        issues = []
        # Double spaces
        if "  " in text:
            issues.append({"category": "fluency", "type": "punctuation", "severity": "minor",
                           "text": "Double space detected"})
        # Repeated punctuation (not in CJK)
        if re.search(r'[.!?]{3,}', text) and lang not in ("zh", "ja", "ko"):
            issues.append({"category": "fluency", "type": "punctuation", "severity": "minor",
                           "text": "Repeated punctuation"})
        # Trailing space before punctuation
        if re.search(r' [.!?,;:]', text):
            issues.append({"category": "fluency", "type": "punctuation", "severity": "minor",
                           "text": "Space before punctuation"})
        return issues

    def _check_locale_conventions(self, text: str, lang: str) -> List[Dict]:
        issues = []
        LATIN_LANGS = ("en", "es", "fr", "de", "pt", "it", "nl")
        # Date format check for Latin languages
        if lang in LATIN_LANGS:
            if re.search(r'\d{4}/\d{2}/\d{2}', text):
                issues.append({"category": "locale_convention", "type": "date_format",
                               "severity": "minor", "text": "Non-standard date format (YYYY/MM/DD)"})
        return issues

    def batch_evaluate(self, pairs: List[Tuple[str, str]], source_lang: str, target_lang: str) -> List[Dict]:
        return [self.evaluate(src, tgt, source_lang, target_lang) for src, tgt in pairs]
