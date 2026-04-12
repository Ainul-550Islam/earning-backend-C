"""
api/ai_engine/NLP_ENGINES/review_analyzer.py
=============================================
Review Analyzer — user reviews ও ratings analyze করো।
App store reviews, in-app feedback, support ratings।
Aspect-based sentiment, trend analysis।
"""
import logging, re
from typing import List, Dict
from .sentiment_analyzer import SentimentAnalyzer
from .entity_extractor import KeywordExtractor
logger = logging.getLogger(__name__)

class ReviewAnalyzer:
    def __init__(self):
        self.sentiment  = SentimentAnalyzer()
        self.keywords   = KeywordExtractor()

    def analyze(self, review_text: str, rating: float = None) -> dict:
        sent_result   = self.sentiment.analyze(review_text)
        kws           = self.keywords.extract(review_text, top_n=8)
        aspects       = self._extract_aspects(review_text)
        predicted_rat = self._predict_rating(sent_result['sentiment_score'])
        is_constructive = len(review_text.split()) >= 10 and (aspects or kws)
        return {
            'sentiment':        sent_result['sentiment'],
            'sentiment_score':  sent_result['sentiment_score'],
            'confidence':       sent_result['confidence'],
            'keywords':         kws,
            'aspects_mentioned': aspects,
            'predicted_rating': predicted_rat,
            'actual_rating':    rating,
            'rating_mismatch':  abs(predicted_rat - rating) > 1.5 if rating else False,
            'is_constructive':  is_constructive,
            'word_count':       len(review_text.split()),
            'language':         sent_result.get('language', 'en'),
        }

    def _predict_rating(self, score: float) -> float:
        raw = 3.0 + score * 2.0
        return round(max(1.0, min(5.0, raw)), 1)

    def _extract_aspects(self, text: str) -> Dict[str, str]:
        aspect_kws = {
            'payment':  ['payment','payout','withdraw','money','টাকা','পেমেন্ট','উইথড্রয়াল'],
            'offers':   ['offer','task','reward','অফার','রিওয়ার্ড','কাজ'],
            'app_ui':   ['app','ui','design','interface','অ্যাপ','ডিজাইন'],
            'support':  ['support','help','response','সাপোর্ট','সাহায্য'],
            'speed':    ['fast','slow','speed','lag','দ্রুত','ধীর','স্লো'],
            'earning':  ['earn','income','profit','আয়','ইনকাম','লাভ'],
        }
        text_lower = text.lower()
        found = {}
        for aspect, kws in aspect_kws.items():
            if any(kw in text_lower for kw in kws):
                window_texts = []
                for kw in kws:
                    if kw in text_lower:
                        idx = text_lower.find(kw)
                        window_texts.append(text_lower[max(0,idx-30):idx+80])
                if window_texts:
                    combined = ' '.join(window_texts)
                    result = self.sentiment.analyze(combined)
                    found[aspect] = result['sentiment']
        return found

    def aggregate_reviews(self, reviews: List[Dict]) -> dict:
        if not reviews: return {}
        total   = len(reviews)
        ratings = [r.get('rating', 3) for r in reviews if r.get('rating')]
        texts   = [r.get('text', '') for r in reviews if r.get('text')]
        agg_sent = self.sentiment.aggregate_sentiment(texts) if texts else {}
        avg_rating = sum(ratings)/len(ratings) if ratings else 0
        all_keywords = []
        for text in texts[:50]:
            all_keywords.extend(self.keywords.extract(text, 5))
        freq = {}
        for kw in all_keywords:
            freq[kw] = freq.get(kw, 0) + 1
        top_kws = sorted(freq, key=freq.get, reverse=True)[:10]
        return {
            'total_reviews':  total,
            'avg_rating':     round(avg_rating, 2),
            'sentiment':      agg_sent,
            'top_keywords':   top_kws,
            'rating_dist':    {str(i): ratings.count(i) for i in range(1,6)},
        }

    def detect_fake_reviews(self, reviews: List[Dict]) -> List[Dict]:
        flagged = []
        for r in reviews:
            text = r.get('text', '')
            rating = r.get('rating', 3)
            flags = []
            sent = self.sentiment.analyze(text)
            if rating == 5 and sent['sentiment'] == 'negative': flags.append('rating_sentiment_mismatch')
            if len(text.split()) < 3: flags.append('too_short')
            if text.count('!') > 5: flags.append('excessive_exclamation')
            if flags:
                flagged.append({**r, 'fake_flags': flags, 'is_suspicious': True})
        return flagged
