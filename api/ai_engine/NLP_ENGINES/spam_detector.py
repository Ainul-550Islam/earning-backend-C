"""
api/ai_engine/NLP_ENGINES/spam_detector.py
==========================================
Spam Detector — text/message spam detection।
Platform content, user messages, offer titles।
Bengali + English spam patterns।
"""
import re, logging
from typing import List, Dict
logger = logging.getLogger(__name__)

SPAM_PATTERNS = [
    r"\bwin\s+(?:now|free|today)\b",
    r"\bclick\s+here\b",
    r"\bfree\s+money\b",
    r"\b(?:urgent|act\s+now|limited\s+time)\b",
    r"\b100%\s+(?:free|guaranteed)\b",
    r"\b(?:earn|make)\s+\$?\d+\s+(?:per\s+day|daily|weekly)\b",
    r"\b(?:crypto|bitcoin|investment)\s+opportunity\b",
    r"\bwork\s+from\s+home\b.{0,30}\beasy\b",
    r"(?:আয়|উপার্জন).{0,20}(?:ঘরে|বাসায়).{0,20}(?:সহজ|টাকা)",
]

SPAM_KEYWORDS = [
    "spam", "scam", "phishing", "malware", "hack", "illegal",
    "pyramid", "ponzi", "guaranteed profit", "no risk",
    "offshore account", "money laundering", "fake",
]

class SpamDetector:
    """Spam detection engine।"""

    def detect(self, text: str) -> dict:
        if not text or not text.strip():
            return {"is_spam": False, "confidence": 0.0, "flags": []}

        text_lower = text.lower()
        flags   = []
        score   = 0.0

        # Pattern matching
        for pattern in SPAM_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                score += 0.25
                flags.append(f"spam_pattern: {pattern[:30]}")

        # Keyword matching
        for kw in SPAM_KEYWORDS:
            if kw in text_lower:
                score += 0.20
                flags.append(f"spam_keyword: {kw}")

        # Excessive punctuation/caps
        if text.count("!") > 5:
            score += 0.15; flags.append("excessive_exclamation")
        if sum(1 for c in text if c.isupper()) / max(len(text), 1) > 0.5:
            score += 0.15; flags.append("excessive_caps")

        # URL spam
        urls = re.findall(r"http[s]?://\S+", text)
        if len(urls) > 3:
            score += 0.20; flags.append("multiple_urls")

        # Phone number spam
        phones = re.findall(r"\b(?:\+?88)?01[3-9]\d{8}\b", text)
        if len(phones) > 2:
            score += 0.10; flags.append("multiple_phone_numbers")

        score = min(1.0, score)
        return {
            "is_spam":    score >= 0.50,
            "confidence": round(score, 4),
            "severity":   "high" if score >= 0.75 else "medium" if score >= 0.50 else "low",
            "flags":      flags[:5],
            "url_count":  len(urls),
            "method":     "rule_based",
        }

    def classify_spam_type(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["earn", "money", "income", "profit", "investment"]):
            return "financial_spam"
        if any(w in text_lower for w in ["casino", "lottery", "win", "prize"]):
            return "lottery_spam"
        if any(w in text_lower for w in ["click", "download", "install", "malware"]):
            return "phishing_spam"
        if any(w in text_lower for w in ["buy", "sale", "discount", "offer", "product"]):
            return "commercial_spam"
        return "generic_spam"

    def batch_detect(self, texts: List[str]) -> List[Dict]:
        return [self.detect(t) for t in texts]

    def filter_spam(self, texts: List[str]) -> List[str]:
        return [t for t in texts if not self.detect(t)["is_spam"]]

    def spam_statistics(self, texts: List[str]) -> dict:
        results  = self.batch_detect(texts)
        spam     = [r for r in results if r["is_spam"]]
        return {
            "total":      len(texts),
            "spam_count": len(spam),
            "spam_rate":  round(len(spam) / max(len(texts), 1), 4),
            "high_confidence_spam": sum(1 for r in spam if r["confidence"] >= 0.75),
        }
