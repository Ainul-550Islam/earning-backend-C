"""
api/ai_engine/NLP_ENGINES/sentiment_analyzer.py
================================================
Sentiment Analyzer — text positive/negative/neutral detection।
User reviews, feedback, support tickets, social media।
Bengali + English language support।
"""
import re, logging
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)

POSITIVE_WORDS = {
    "en": ["good","great","excellent","amazing","love","best","helpful","easy","fast",
           "awesome","perfect","wonderful","fantastic","brilliant","superb","outstanding"],
    "bn": ["ভালো","চমৎকার","অসাধারণ","সুন্দর","দারুণ","মজার","উপকারী","সহজ","দ্রুত"],
}
NEGATIVE_WORDS = {
    "en": ["bad","worst","terrible","horrible","slow","broken","issue","problem","error",
           "fail","hate","awful","poor","disappointing","useless","frustrating"],
    "bn": ["খারাপ","ভয়ঙ্কর","সমস্যা","ভুল","ব্যর্থ","হতাশ","বাজে","নিম্নমান"],
}

class SentimentAnalyzer:
    """Multi-method sentiment analysis engine।"""

    def analyze(self, text: str, method: str = "auto") -> dict:
        if not text or not text.strip():
            return self._neutral_result()
        if method == "transformer":
            result = self._transformer_analyze(text)
            if result: return result
        if method == "openai" or method == "auto":
            try:
                result = self._openai_analyze(text)
                if result: return result
            except Exception: pass
        return self._rule_analyze(text)

    def _rule_analyze(self, text: str) -> dict:
        text_lower = text.lower()
        lang       = "bn" if re.search(r"[ঀ-৿]", text) else "en"
        pos_words  = POSITIVE_WORDS.get(lang, POSITIVE_WORDS["en"])
        neg_words  = NEGATIVE_WORDS.get(lang, NEGATIVE_WORDS["en"])
        pos_count  = sum(1 for w in pos_words if w in text_lower)
        neg_count  = sum(1 for w in neg_words if w in text_lower)
        total      = pos_count + neg_count or 1
        score      = (pos_count - neg_count) / total
        sentiment  = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
        return {
            "sentiment":      sentiment,
            "score":          round(score, 4),
            "confidence":     round(abs(score), 4),
            "positive_words": pos_count,
            "negative_words": neg_count,
            "language":       lang,
            "method":         "rule_based",
        }

    def _transformer_analyze(self, text: str) -> Optional[dict]:
        try:
            from transformers import pipeline
            analyzer = pipeline("sentiment-analysis",
                                model="nlptown/bert-base-multilingual-uncased-sentiment")
            result   = analyzer(text[:512])[0]
            label    = result["label"]
            score    = float(result["score"])
            stars    = int(label.split()[0])
            sentiment = "positive" if stars >= 4 else "negative" if stars <= 2 else "neutral"
            return {"sentiment": sentiment, "score": round((stars - 3) / 2, 4),
                    "confidence": round(score, 4), "stars": stars, "method": "transformer"}
        except Exception as e:
            logger.debug(f"Transformer sentiment failed: {e}")
            return None

    def _openai_analyze(self, text: str) -> Optional[dict]:
        from ..INTEGRATIONS.openai_integration import OpenAIIntegration
        client = OpenAIIntegration()
        prompt = f"Analyze the sentiment of this text. Reply ONLY with JSON: {{sentiment: positive/negative/neutral, score: -1.0 to 1.0, confidence: 0.0-1.0}}\n\nText: {text[:500]}"
        result = client.complete(prompt, max_tokens=100)
        content = result.get("content", "")
        import json
        clean = content.strip().strip("```json").strip("```").strip()
        data  = json.loads(clean)
        return {**data, "method": "openai"}

    def analyze_batch(self, texts: List[str]) -> List[dict]:
        return [self.analyze(text) for text in texts]

    def aggregate(self, results: List[dict]) -> dict:
        if not results: return {}
        pos = sum(1 for r in results if r.get("sentiment") == "positive")
        neg = sum(1 for r in results if r.get("sentiment") == "negative")
        total = len(results)
        return {
            "positive_count":   pos,
            "negative_count":   neg,
            "neutral_count":    total - pos - neg,
            "positive_rate":    round(pos / total, 4),
            "negative_rate":    round(neg / total, 4),
            "avg_score":        round(sum(r.get("score", 0) for r in results) / total, 4),
            "overall_sentiment": "positive" if pos > neg else "negative" if neg > pos else "neutral",
        }

    def _neutral_result(self) -> dict:
        return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "method": "empty"}
