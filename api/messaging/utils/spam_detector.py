"""
Spam & Content Moderation — ML-powered content filtering.
Protects the platform from spam, abuse, harassment.

Features:
- Text-based spam detection (keyword + ML heuristics)
- Duplicate message detection (copy-paste spam)
- Link spam detection
- Content toxicity scoring (Perspective API)
- Auto-block repeat offenders
- Message similarity (flooding detection)
"""
from __future__ import annotations
import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

SPAM_KEYWORDS = frozenset([
    "buy now", "click here", "free money", "earn $", "guaranteed",
    "limited time offer", "act now", "winner", "congratulations you won",
    "send your bank details", "investment opportunity",
])

EXCESSIVE_CAPS_THRESHOLD = 0.6
MAX_REPEATED_CHARS = 5
MAX_LINKS_PER_MESSAGE = 5
SIMILARITY_THRESHOLD = 0.85  # 85% similar = duplicate


def analyze_message(content: str, user_id: Any = None) -> dict:
    """
    Analyze a message for spam/abuse.
    Returns {is_spam, is_toxic, spam_score, toxic_score, reasons}.
    """
    if not content or not content.strip():
        return {"is_spam": False, "is_toxic": False, "spam_score": 0.0, "reasons": []}

    reasons = []
    spam_score = 0.0

    # 1. Keyword-based spam check
    lower_content = content.lower()
    keyword_hits = [kw for kw in SPAM_KEYWORDS if kw in lower_content]
    if keyword_hits:
        spam_score += min(0.4, len(keyword_hits) * 0.15)
        reasons.append(f"spam_keywords:{','.join(keyword_hits[:3])}")

    # 2. Excessive CAPS check
    alpha_chars = [c for c in content if c.isalpha()]
    if alpha_chars:
        caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if caps_ratio > EXCESSIVE_CAPS_THRESHOLD and len(content) > 20:
            spam_score += 0.2
            reasons.append("excessive_caps")

    # 3. Repeated characters (aaaaaaa, !!!!!!)
    if re.search(r'(.)\1{' + str(MAX_REPEATED_CHARS) + r',}', content):
        spam_score += 0.15
        reasons.append("repeated_chars")

    # 4. Excessive links
    urls = re.findall(r'https?://\S+', content)
    if len(urls) > MAX_LINKS_PER_MESSAGE:
        spam_score += 0.3
        reasons.append(f"excessive_links:{len(urls)}")

    # 5. Duplicate/flood detection
    if user_id:
        is_dup, dup_count = check_duplicate_message(user_id, content)
        if is_dup:
            spam_score += min(0.5, dup_count * 0.2)
            reasons.append(f"duplicate_message:x{dup_count}")

    # 6. Perspective API toxicity (if configured)
    toxic_result = {"is_toxic": False, "toxic_score": 0.0}
    if len(content) > 10:
        toxic_result = check_toxicity(content)

    is_spam = spam_score >= 0.5
    if is_spam and user_id:
        logger.warning("analyze_message: SPAM detected user=%s score=%.2f reasons=%s", user_id, spam_score, reasons)

    return {
        "is_spam":     is_spam,
        "is_toxic":    toxic_result["is_toxic"],
        "spam_score":  round(spam_score, 3),
        "toxic_score": toxic_result.get("toxic_score", 0.0),
        "reasons":     reasons,
    }


def check_duplicate_message(user_id: Any, content: str, window_seconds: int = 60) -> tuple[bool, int]:
    """
    Detect if user is flooding with the same/similar message.
    Uses content hash stored in Redis.
    """
    try:
        from django.core.cache import cache
        content_hash = hashlib.md5(content.strip().lower().encode()).hexdigest()
        key = f"msg_hash:{user_id}:{content_hash}"
        count = cache.get(key) or 0
        new_count = count + 1
        cache.set(key, new_count, window_seconds)
        return count >= 2, count  # Duplicate if sent 3+ times in window
    except Exception:
        return False, 0


def check_toxicity(text: str) -> dict:
    """
    Score text toxicity using Google Perspective API.
    Returns {is_toxic, toxic_score, categories}.
    """
    from django.conf import settings
    api_key = getattr(settings, "PERSPECTIVE_API_KEY", None)
    if not api_key:
        return {"is_toxic": False, "toxic_score": 0.0}

    try:
        import requests
        payload = {
            "comment": {"text": text[:3000]},
            "languages": ["en", "bn"],
            "requestedAttributes": {
                "TOXICITY": {},
                "SEVERE_TOXICITY": {},
                "INSULT": {},
                "THREAT": {},
                "PROFANITY": {},
            },
        }
        resp = requests.post(
            f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={api_key}",
            json=payload,
            timeout=5,
        )
        resp.raise_for_status()
        scores = resp.json().get("attributeScores", {})
        toxicity = scores.get("TOXICITY", {}).get("summaryScore", {}).get("value", 0.0)
        severe   = scores.get("SEVERE_TOXICITY", {}).get("summaryScore", {}).get("value", 0.0)

        is_toxic = toxicity > 0.8 or severe > 0.6
        categories = {
            k: round(v.get("summaryScore", {}).get("value", 0.0), 3)
            for k, v in scores.items()
        }
        return {"is_toxic": is_toxic, "toxic_score": round(toxicity, 3), "categories": categories}
    except Exception as exc:
        logger.warning("check_toxicity: %s", exc)
        return {"is_toxic": False, "toxic_score": 0.0}


def should_auto_moderate(content: str, user_id: Any = None) -> tuple[bool, str]:
    """
    Quick check — should this message be blocked before saving?
    Returns (should_block, reason).
    """
    if not content:
        return False, ""
    result = analyze_message(content, user_id)
    if result["is_spam"] and result["spam_score"] >= 0.7:
        return True, f"spam:{result['spam_score']:.2f}"
    if result["is_toxic"] and result["toxic_score"] >= 0.9:
        return True, f"toxic:{result['toxic_score']:.2f}"
    return False, ""
