"""
api/ai_engine/NLP_ENGINES/intent_classifier.py
===============================================
Intent Classifier — user message intent classify করো।
Support tickets, chat messages, feedback forms।
Multi-class intent with confidence scores।
"""
import logging, re
from typing import Dict, List
logger = logging.getLogger(__name__)

INTENT_RULES: Dict[str, List[str]] = {
    'complaint':     ['problem','issue','not working','broken','error','failed','wrong','bad','সমস্যা','কাজ করছে না','ভুল'],
    'withdrawal':    ['withdraw','cashout','payment','payout','বের করতে','টাকা তুলতে','উত্তোলন','ক্যাশ আউট'],
    'inquiry':       ['how','what','when','where','why','can i','is it','জানতে চাই','কিভাবে','কী করব'],
    'request':       ['please','help','need','want','request','দরকার','সাহায্য','চাই','করতে চাই'],
    'feedback':      ['suggest','improve','feedback','opinion','idea','মতামত','পরামর্শ','উন্নতি'],
    'appreciation':  ['thanks','thank you','great','awesome','love it','ধন্যবাদ','চমৎকার','অনেক ভালো'],
    'referral':      ['refer','invite','friend','referral','রেফার','বন্ধু','আমন্ত্রণ'],
    'account':       ['account','profile','password','login','register','একাউন্ট','পাসওয়ার্ড','লগইন'],
    'kyc':           ['kyc','verify','document','id','national id','nid','কেওয়াইসি','ভেরিফাই','পরিচয়'],
    'offer':         ['offer','task','earn','complete','অফার','আয়','কাজ','সম্পন্ন'],
}

class IntentClassifier:
    def classify(self, text: str, top_k: int = 3) -> dict:
        text_lower = text.lower()
        scores: Dict[str, float] = {}
        for intent, keywords in INTENT_RULES.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits > 0:
                scores[intent] = hits
        if not scores:
            return {'intent':'general','confidence':0.40,'all_intents':{},'top_intents':[{'intent':'general','confidence':0.40}]}
        total = sum(scores.values())
        normalized = {k: round(v/total,4) for k,v in sorted(scores.items(), key=lambda x:x[1], reverse=True)}
        best = list(normalized.keys())[0]
        conf = min(0.95, 0.50 + normalized[best]*0.45)
        top_k_list = [{'intent':k,'confidence':round(v*conf,4)} for k,v in list(normalized.items())[:top_k]]
        return {
            'intent':     best,
            'confidence': round(conf,4),
            'all_intents': normalized,
            'top_intents': top_k_list,
        }

    def route_to_team(self, intent: str) -> str:
        routing = {
            'complaint': 'support_team',
            'withdrawal': 'payment_team',
            'kyc': 'verification_team',
            'account': 'account_team',
            'offer': 'offer_team',
            'feedback': 'product_team',
        }
        return routing.get(intent, 'general_support')

    def priority_from_intent(self, intent: str, sentiment: str = 'neutral') -> str:
        urgent_intents = {'withdrawal','account','kyc'}
        if intent in urgent_intents and sentiment == 'negative': return 'urgent'
        if intent == 'complaint': return 'high'
        if intent in urgent_intents: return 'medium'
        return 'low'

    def classify_bulk(self, texts: List[str]) -> List[dict]:
        return [{'text': t[:50], **self.classify(t)} for t in texts]
