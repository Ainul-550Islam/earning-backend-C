"""
api/ai_engine/INTEGRATIONS/openai_integration.py
=================================================
OpenAI GPT Integration — text generation, embeddings।
"""

import logging
from ..config import ai_config

logger = logging.getLogger(__name__)


class OpenAIIntegration:
    """OpenAI API integration।"""

    def __init__(self):
        self.api_key = ai_config.openai_api_key
        self.client  = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            logger.warning("openai package not installed. pip install openai")

    def complete(self, prompt: str, model: str = 'gpt-4o-mini',
                 max_tokens: int = 500, temperature: float = 0.7) -> str:
        if not self.client:
            return ''
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return ''

    def embed(self, text: str, model: str = 'text-embedding-3-small') -> list:
        if not self.client:
            return []
        try:
            response = self.client.embeddings.create(
                model=model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            return []

    def analyze_sentiment(self, text: str) -> dict:
        prompt = f"""Analyze the sentiment of this text. 
Return JSON only: {{"sentiment": "positive/negative/neutral", "score": 0.0-1.0, "reason": "brief reason"}}

Text: {text[:1000]}"""
        result = self.complete(prompt, max_tokens=100, temperature=0.1)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {'sentiment': 'neutral', 'score': 0.5}

    def generate_insight(self, data_summary: str) -> str:
        prompt = f"""You are a business analyst. Based on this data, generate a concise actionable insight in 2-3 sentences.

Data: {data_summary[:2000]}

Insight:"""
        return self.complete(prompt, max_tokens=200)


"""
api/ai_engine/INTEGRATIONS/anthropic_integration.py
====================================================
Anthropic Claude Integration — AI text analysis।
"""


class AnthropicIntegration:
    """Anthropic Claude API integration।"""

    def __init__(self):
        self.api_key = ai_config.anthropic_api_key
        self.client  = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            logger.warning("anthropic package not installed. pip install anthropic")

    def complete(self, prompt: str, model: str = 'claude-haiku-4-5-20251001',
                 max_tokens: int = 500) -> str:
        if not self.client:
            return ''
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            return ''

    def analyze_text(self, text: str, task: str = 'sentiment') -> dict:
        prompt = f"""Task: {task} analysis.
Return JSON only with relevant fields.

Text: {text[:2000]}"""
        result = self.complete(prompt, max_tokens=200)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {}

    def generate_user_insight(self, user_data: dict) -> str:
        prompt = f"""Based on this user data, write a brief actionable retention insight (2 sentences max):
{user_data}"""
        return self.complete(prompt, max_tokens=150)
