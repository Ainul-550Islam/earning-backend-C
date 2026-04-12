"""
api/ai_engine/NLP_ENGINES/question_answering.py
================================================
Question Answering — context-based Q&A।
Help center, FAQ automation, support chatbot।
"""
import logging
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class QuestionAnswering:
    """Question answering engine।"""

    # Common FAQ answers
    FAQ_DB: Dict[str, str] = {
        'withdraw':      'Minimum withdrawal is 100 BDT. Processing takes 1-3 business days.',
        'kyc':           'Submit NID/Passport photo. Verification takes 24-48 hours.',
        'referral':      'Share your referral code. Earn bonus when friends complete first offer.',
        'coin':          'Coins are earned by completing offers. 1 Coin = 1 BDT.',
        'offer':         'Browse available offers, click, complete the required action.',
        'payment':       'We support bKash, Nagad, Rocket, bank transfer.',
        'banned':        'Contact support with your account ID. We review within 48 hours.',
        'password':      'Use "Forgot Password" on the login page.',
    }

    def answer(self, question: str, context: str = None,
               method: str = 'auto') -> dict:
        """Question এর answer generate করো।"""
        if not question:
            return {'answer': '', 'confidence': 0.0}

        # Context provided হলে extractive QA
        if context:
            return self._extractive_qa(question, context)

        # FAQ match try করো
        faq_result = self._faq_match(question)
        if faq_result['confidence'] >= 0.70:
            return faq_result

        # LLM-based answer
        return self._llm_answer(question, context)

    def _faq_match(self, question: str) -> dict:
        """FAQ database থেকে answer খুঁজো।"""
        q_lower = question.lower()
        best_match = None
        best_score = 0.0

        for keyword, answer in self.FAQ_DB.items():
            if keyword in q_lower:
                score = len(keyword) / max(len(q_lower), 1)
                if score > best_score:
                    best_score = score
                    best_match = answer

        if best_match:
            return {'answer': best_match, 'confidence': round(min(0.95, best_score * 3), 4),
                    'method': 'faq', 'source': 'faq_database'}
        return {'answer': '', 'confidence': 0.0, 'method': 'faq'}

    def _extractive_qa(self, question: str, context: str) -> dict:
        """Context থেকে extractive QA।"""
        try:
            from transformers import pipeline
            qa_pipeline = pipeline('question-answering',
                                    model='distilbert-base-cased-distilled-squad')
            result = qa_pipeline(question=question, context=context)
            return {
                'answer':     result['answer'],
                'confidence': round(float(result['score']), 4),
                'method':     'extractive',
                'start':      result.get('start'),
                'end':        result.get('end'),
            }
        except ImportError:
            return self._simple_extractive(question, context)
        except Exception as e:
            logger.error(f"QA pipeline error: {e}")
            return self._simple_extractive(question, context)

    def _simple_extractive(self, question: str, context: str) -> dict:
        """Simple sentence-based extractive QA।"""
        q_words  = set(question.lower().split())
        sentences = context.split('.')
        best, best_score = '', 0.0
        for sent in sentences:
            s_words  = set(sent.lower().split())
            overlap  = len(q_words & s_words) / max(len(q_words), 1)
            if overlap > best_score:
                best_score = overlap
                best       = sent.strip()
        return {'answer': best, 'confidence': round(best_score, 4), 'method': 'simple_extractive'}

    def _llm_answer(self, question: str, context: Optional[str]) -> dict:
        """LLM-based generative answer।"""
        try:
            from ..INTEGRATIONS.openai_integration import OpenAIIntegration
            client = OpenAIIntegration()
            system = "You are a helpful customer support assistant for an earning/reward platform in Bangladesh. Answer concisely."
            prompt = f"Question: {question}"
            if context:
                prompt = f"Context: {context}\n\nQuestion: {question}"
            result = client.complete(prompt, system_prompt=system, max_tokens=200)
            return {
                'answer':     result.get('content', ''),
                'confidence': 0.75,
                'method':     'llm',
            }
        except Exception as e:
            logger.error(f"LLM QA error: {e}")
            return {'answer': 'Please contact our support team for assistance.',
                    'confidence': 0.50, 'method': 'fallback'}

    def batch_answer(self, questions: List[str],
                     context: str = None) -> List[Dict]:
        """Multiple questions answer করো।"""
        return [self.answer(q, context) for q in questions]

    def add_faq(self, keyword: str, answer: str):
        """New FAQ entry add করো।"""
        self.FAQ_DB[keyword.lower()] = answer
        logger.info(f"FAQ added: {keyword}")
