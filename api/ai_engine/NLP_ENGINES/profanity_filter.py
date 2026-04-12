"""
api/ai_engine/NLP_ENGINES/profanity_filter.py
=============================================
Profanity Filter — offensive content detection ও censorship।
Multi-language support (English + Bengali)।
User reviews, comments, chat messages, usernames filter করো।
Marketing platform এর content safety এর জন্য।
"""

import re
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


# ── Word lists ─────────────────────────────────────────────────────────────
# Production এ comprehensive licensed word list ব্যবহার করো (e.g., better-profanity)
_ENGLISH_PATTERNS = [
    r'\bf+u+c+k+\w*\b',
    r'\bs+h+i+t+\w*\b',
    r'\ba+s+s+h+o+l+e+\b',
    r'\bb+i+t+c+h+\w*\b',
    r'\bc+u+n+t+\b',
    r'\bd+a+m+n+\b',
    r'\bb+a+s+t+a+r+d+\b',
    r'\bc+r+a+p+\b',
    r'\bp+i+s+s+\w*\b',
    r'\bw+h+o+r+e+\b',
]

_BENGALI_PATTERNS = [
    r'মাগী', r'হারামি', r'কুত্তা', r'শালা', r'বেশ্যা',
    r'মাদার', r'বাস্টার্ড', r'নষ্ট', r'ছাগল',
]

_SEVERITY_MAP = {
    'extreme':   ['f+u+c+k', 'c+u+n+t', 'w+h+o+r+e', 'বেশ্যা'],
    'high':      ['b+i+t+c+h', 'a+s+s+h+o+l+e', 'b+a+s+t+a+r+d', 'হারামি'],
    'medium':    ['s+h+i+t', 'd+a+m+n', 'c+r+a+p', 'শালা'],
    'low':       ['p+i+s+s', 'ছাগল'],
}

# ── Replacement strategies ─────────────────────────────────────────────────
_REPLACEMENT = {
    'asterisk':  lambda w: w[0] + '*' * (len(w) - 2) + w[-1] if len(w) > 2 else '***',
    'full':      lambda w: '***',
    'emoji':     lambda w: '🚫',
    'blank':     lambda w: '',
}


class ProfanityFilter:
    """
    Comprehensive profanity detection ও filtering।
    Marketing platform এর user content safety layer।
    """

    def __init__(self, sensitivity: str = 'medium',
                 replacement: str = 'asterisk',
                 custom_words: List[str] = None):
        """
        sensitivity: 'low' | 'medium' | 'high' | 'strict'
        replacement: 'asterisk' | 'full' | 'emoji' | 'blank'
        """
        self.sensitivity  = sensitivity
        self.replacement  = replacement
        self.custom_words = custom_words or []
        self._compiled    = self._compile_patterns()

    def _compile_patterns(self) -> List[re.Pattern]:
        """Patterns compile করো।"""
        patterns = []
        all_patterns = _ENGLISH_PATTERNS + _BENGALI_PATTERNS
        for p in all_patterns:
            try:
                patterns.append(re.compile(p, re.IGNORECASE | re.UNICODE))
            except re.error:
                pass
        # Custom words
        for word in self.custom_words:
            try:
                patterns.append(re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE))
            except re.error:
                pass
        return patterns

    def check(self, text: str) -> dict:
        """Text এ profanity আছে কিনা check করো।"""
        if not text:
            return self._clean_result()

        text_lower = text.lower()
        matches    = []
        severity   = 'none'

        for pattern in self._compiled:
            found = pattern.findall(text_lower)
            if found:
                matches.extend(found)

        # Severity determination
        if matches:
            max_sev = 'low'
            for match in matches:
                for sev, keywords in _SEVERITY_MAP.items():
                    if any(re.search(k, match, re.IGNORECASE) for k in keywords):
                        if ['low', 'medium', 'high', 'extreme'].index(sev) > \
                           ['low', 'medium', 'high', 'extreme'].index(max_sev):
                            max_sev = sev
            severity = max_sev

        # Sensitivity filtering
        blocked = self._should_block(severity)

        return {
            'has_profanity':   len(matches) > 0,
            'is_flagged':      blocked,
            'severity':        severity,
            'matches_count':   len(matches),
            'matched_words':   list(set(matches))[:5],  # Max 5 for privacy
            'confidence':      min(1.0, len(matches) * 0.3 + 0.4) if matches else 0.0,
            'action':          'block' if blocked else 'allow',
        }

    def _should_block(self, severity: str) -> bool:
        """Sensitivity level অনুযায়ী block করবে কিনা।"""
        thresholds = {
            'strict': ['low', 'medium', 'high', 'extreme'],
            'high':   ['medium', 'high', 'extreme'],
            'medium': ['high', 'extreme'],
            'low':    ['extreme'],
        }
        blocked_levels = thresholds.get(self.sensitivity, ['high', 'extreme'])
        return severity in blocked_levels

    def clean(self, text: str) -> str:
        """Profanity replace করে cleaned text return করো।"""
        if not text:
            return text

        cleaned    = text
        replacer   = _REPLACEMENT.get(self.replacement, _REPLACEMENT['asterisk'])

        for pattern in self._compiled:
            def replace_match(m):
                return replacer(m.group(0))
            cleaned = pattern.sub(replace_match, cleaned)

        return cleaned

    def clean_and_check(self, text: str) -> Tuple[str, dict]:
        """Check + clean একসাথে।"""
        check_result = self.check(text)
        cleaned_text = self.clean(text) if check_result['has_profanity'] else text
        return cleaned_text, check_result

    def check_username(self, username: str) -> dict:
        """Username profanity check — stricter rules।"""
        result = self.check(username)

        # Additional username-specific checks
        leet_speak = self._detect_leet_speak(username)
        if leet_speak:
            result['has_profanity'] = True
            result['is_flagged']    = True
            result['flags']         = result.get('flags', []) + ['leet_speak_profanity']

        return result

    def _detect_leet_speak(self, text: str) -> bool:
        """1337 speak detection (e.g., sh1t, f4ck)।"""
        leet_map = {'@': 'a', '4': 'a', '3': 'e', '1': 'i', '0': 'o',
                    '5': 's', '7': 't', '$': 's', '!': 'i', '+': 't'}
        decoded = text.lower()
        for leet, normal in leet_map.items():
            decoded = decoded.replace(leet, normal)
        return self.check(decoded)['has_profanity'] and decoded != text.lower()

    def bulk_check(self, texts: List[str]) -> List[dict]:
        """Multiple texts একসাথে check করো।"""
        return [self.check(t) for t in texts]

    def filter_list(self, texts: List[str]) -> Tuple[List[str], List[int]]:
        """List থেকে clean texts এবং flagged indices return করো।"""
        clean  = []
        flagged_idx = []
        for i, text in enumerate(texts):
            result = self.check(text)
            if result['is_flagged']:
                flagged_idx.append(i)
                clean.append(self.clean(text))
            else:
                clean.append(text)
        return clean, flagged_idx

    def get_stats(self, texts: List[str]) -> dict:
        """Text collection এর profanity statistics।"""
        results  = self.bulk_check(texts)
        total    = len(results)
        flagged  = sum(1 for r in results if r['is_flagged'])
        by_sev   = {}
        for r in results:
            sev = r.get('severity', 'none')
            by_sev[sev] = by_sev.get(sev, 0) + 1

        return {
            'total':           total,
            'clean':           total - flagged,
            'flagged':         flagged,
            'flag_rate':       round(flagged / max(total, 1), 4),
            'by_severity':     by_sev,
            'needs_moderation': flagged > 0,
        }

    def add_custom_word(self, word: str):
        """Custom blocked word add করো।"""
        if word not in self.custom_words:
            self.custom_words.append(word.lower())
            try:
                self._compiled.append(
                    re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
                )
            except re.error:
                pass

    def _clean_result(self) -> dict:
        return {
            'has_profanity': False, 'is_flagged': False,
            'severity': 'none', 'matches_count': 0,
            'matched_words': [], 'confidence': 0.0, 'action': 'allow',
        }
