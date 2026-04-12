# utils/fuzzy.py
"""
Fuzzy string matching algorithms for Translation Memory.
Implements Levenshtein distance + Trigram similarity.
Used by TranslationMemoryService for fuzzy TM lookup.
No external dependencies — pure Python.
"""
from typing import List, Tuple, Optional
import re


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Classic Levenshtein edit distance.
    Returns minimum edits (insert/delete/replace) to transform s1 → s2.
    O(m*n) time, O(min(m,n)) space.
    """
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    # Use shorter string as column to minimize memory
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions  = prev_row[j + 1] + 1
            deletions   = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def levenshtein_similarity(s1: str, s2: str) -> float:
    """
    Levenshtein similarity as a percentage (0.0 – 100.0).
    100.0 = identical strings.
    """
    if not s1 and not s2:
        return 100.0
    if not s1 or not s2:
        return 0.0

    s1_n = _normalize(s1)
    s2_n = _normalize(s2)

    if s1_n == s2_n:
        return 100.0

    distance = levenshtein_distance(s1_n, s2_n)
    max_len = max(len(s1_n), len(s2_n))
    return round((1 - distance / max_len) * 100, 2)


def _get_trigrams(text: str) -> set:
    """Extract character trigrams from text. "hello" → {' he', 'hel', 'ell', 'llo', 'lo '}"""
    padded = ' ' + text + ' '
    return {padded[i:i+3] for i in range(len(padded) - 2)}


def trigram_similarity(s1: str, s2: str) -> float:
    """
    Trigram (3-gram) similarity — better than Levenshtein for long texts.
    Uses Sørensen–Dice coefficient on character trigrams.
    Returns 0.0 – 100.0.
    """
    if not s1 and not s2:
        return 100.0
    if not s1 or not s2:
        return 0.0

    s1_n = _normalize(s1)
    s2_n = _normalize(s2)

    if s1_n == s2_n:
        return 100.0

    t1 = _get_trigrams(s1_n)
    t2 = _get_trigrams(s2_n)

    if not t1 or not t2:
        return 0.0

    intersection = len(t1 & t2)
    dice = (2 * intersection) / (len(t1) + len(t2))
    return round(dice * 100, 2)


def combined_similarity(s1: str, s2: str, lev_weight: float = 0.4, tri_weight: float = 0.6) -> float:
    """
    Weighted combination of Levenshtein + Trigram similarity.
    Trigram is weighted higher — better for translation memory use cases.
    Returns 0.0 – 100.0.
    """
    lev = levenshtein_similarity(s1, s2)
    tri = trigram_similarity(s1, s2)
    return round(lev_weight * lev + tri_weight * tri, 2)


def best_match_from_list(
    query: str,
    candidates: List[str],
    min_score: float = 70.0,
    algorithm: str = 'combined',
) -> List[Tuple[str, float]]:
    """
    Query text-এর সাথে candidates list-এর fuzzy match করে।
    Returns list of (candidate, score) sorted by score desc, filtered by min_score.

    algorithm: 'levenshtein' | 'trigram' | 'combined'
    """
    if not query or not candidates:
        return []

    algo_map = {
        'levenshtein': levenshtein_similarity,
        'trigram': trigram_similarity,
        'combined': combined_similarity,
    }
    scorer = algo_map.get(algorithm, combined_similarity)

    scored = []
    for candidate in candidates:
        score = scorer(query, candidate)
        if score >= min_score:
            scored.append((candidate, score))

    scored.sort(key=lambda x: -x[1])
    return scored


def tokenize_for_tm(text: str) -> str:
    """
    Translation Memory-র জন্য text normalize করে।
    Case folding + whitespace normalization + remove extra punctuation.
    """
    return _normalize(text)


def _normalize(text: str) -> str:
    """Internal normalization: lowercase + collapse whitespace"""
    if not text:
        return ''
    # Lowercase
    text = text.lower().strip()
    # Collapse multiple whitespace
    text = re.sub(r'\s+', ' ', text)
    return text
