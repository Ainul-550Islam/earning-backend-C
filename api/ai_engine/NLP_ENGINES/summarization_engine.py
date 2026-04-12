"""
api/ai_engine/NLP_ENGINES/summarization_engine.py
==================================================
Summarization Engine — long text থেকে key points extract করো।
Support tickets, user reviews, feedback, offer descriptions।
Extractive + Abstractive summarization।
"""
import re, logging
from typing import List, Optional
logger = logging.getLogger(__name__)

class SummarizationEngine:
    """Text summarization engine।"""

    def summarize(self, text: str, max_sentences: int = 3,
                  method: str = "auto") -> dict:
        if not text or not text.strip():
            return {"summary": "", "method": "empty"}

        word_count = len(text.split())
        if word_count < 50:
            return {"summary": text, "method": "short_text", "compressed_pct": 0}

        if method in ("llm", "auto") and word_count > 100:
            try:
                result = self._llm_summarize(text, max_sentences)
                if result: return result
            except Exception: pass

        return self._extractive_summarize(text, max_sentences)

    def _llm_summarize(self, text: str, max_sentences: int) -> Optional[dict]:
        from ..INTEGRATIONS.openai_integration import OpenAIIntegration
        client = OpenAIIntegration()
        prompt = f"Summarize the following text in {max_sentences} concise sentences. Keep the most important information:\n\n{text[:3000]}"
        result = client.complete(prompt, max_tokens=300)
        summary = result.get("content", "").strip()
        if not summary: return None
        return {
            "summary":        summary,
            "original_words": len(text.split()),
            "summary_words":  len(summary.split()),
            "compressed_pct": round((1 - len(summary.split()) / max(len(text.split()), 1)) * 100, 1),
            "method":         "llm",
        }

    def _extractive_summarize(self, text: str, max_sentences: int) -> dict:
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        if not sentences:
            return {"summary": text[:500], "method": "truncate"}

        # Score sentences by word frequency
        words = re.findall(r"\b\w{3,}\b", text.lower())
        freq: dict = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        max_freq = max(freq.values()) if freq else 1

        scored = []
        for sent in sentences:
            sent_words = re.findall(r"\b\w{3,}\b", sent.lower())
            score = sum(freq.get(w, 0) / max_freq for w in sent_words) / max(len(sent_words), 1)
            scored.append((score, sent))

        top_sentences = sorted(scored, key=lambda x: x[0], reverse=True)[:max_sentences]
        # Restore original order
        ordered = sorted(top_sentences, key=lambda x: sentences.index(x[1]))
        summary = ". ".join(s[1] for s in ordered) + "."

        return {
            "summary":        summary,
            "original_words": len(text.split()),
            "summary_words":  len(summary.split()),
            "compressed_pct": round((1 - len(summary.split()) / max(len(text.split()), 1)) * 100, 1),
            "method":         "extractive_tfidf",
        }

    def batch_summarize(self, texts: List[str], max_sentences: int = 3) -> List[dict]:
        return [self.summarize(t, max_sentences) for t in texts]

    def summarize_reviews(self, reviews: List[str], max_sentences: int = 5) -> dict:
        combined = " ".join(reviews)
        summary  = self.summarize(combined, max_sentences)
        return {**summary, "review_count": len(reviews)}

    def key_points(self, text: str, n_points: int = 5) -> List[str]:
        result = self.summarize(text, max_sentences=n_points)
        summary = result.get("summary", "")
        points  = [s.strip() for s in re.split(r"[.!?]+", summary) if len(s.strip()) > 10]
        return points[:n_points]
