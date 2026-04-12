"""
api/ai_engine/INTEGRATIONS/anthropic_integration.py
====================================================
Anthropic Claude Integration — Claude API wrapper।
Content moderation, analysis, generation, reasoning।
"""
import logging
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

class AnthropicIntegration:
    """Anthropic Claude API integration।"""

    DEFAULT_MODEL = "claude-sonnet-4-6"
    MAX_TOKENS    = 4096

    def __init__(self):
        from ..config import ai_config
        self.api_key  = ai_config.anthropic_api_key
        self.client   = None
        self._init()

    def _init(self):
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured")
            return
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("Anthropic client initialized")
        except ImportError:
            logger.warning("anthropic not installed. pip install anthropic")

    def complete(self, prompt: str,
                 system_prompt: str = None,
                 model: str = None,
                 max_tokens: int = 1000,
                 temperature: float = 0.7) -> dict:
        if not self.client:
            return {"content": "", "error": "Anthropic not configured"}
        try:
            messages = [{"role": "user", "content": prompt}]
            kwargs   = {
                "model":      model or self.DEFAULT_MODEL,
                "max_tokens": max_tokens,
                "messages":   messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            response = self.client.messages.create(**kwargs)
            content  = response.content[0].text if response.content else ""
            return {
                "content":      content,
                "model":        response.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "stop_reason":  response.stop_reason,
            }
        except Exception as e:
            logger.error(f"Anthropic completion error: {e}")
            return {"content": "", "error": str(e)}

    def analyze_content(self, text: str, task: str = "sentiment") -> dict:
        prompts = {
            "sentiment":  f"Analyze the sentiment of this text. Reply with JSON {{sentiment, score (-1 to 1), confidence}}: {text[:500]}",
            "moderation": f"Check if this content violates community guidelines. Reply with JSON {{safe: bool, issues: [], confidence}}: {text[:500]}",
            "intent":     f"Identify the intent of this text. Reply with JSON {{intent, confidence}}: {text[:500]}",
            "summary":    f"Summarize this text in 2-3 sentences: {text[:2000]}",
        }
        prompt = prompts.get(task, f"Analyze: {text[:500]}")
        result = self.complete(prompt, max_tokens=500)
        content = result.get("content", "")
        if task in ("sentiment", "moderation", "intent"):
            try:
                import json
                clean = content.strip().strip("```json").strip("```").strip()
                return {**json.loads(clean), "provider": "anthropic"}
            except Exception:
                pass
        return {"result": content, "provider": "anthropic"}

    def moderate_content(self, text: str) -> dict:
        return self.analyze_content(text, "moderation")

    def generate_offer_description(self, offer_data: dict) -> str:
        prompt = f"""Write a compelling offer description for this earning platform offer:
Title: {offer_data.get("title", "")}
Category: {offer_data.get("category", "")}
Reward: {offer_data.get("reward_amount", "")} BDT
Difficulty: {offer_data.get("difficulty", "")}

Write 2-3 sentences, persuasive, clear instructions."""
        result = self.complete(prompt, max_tokens=200)
        return result.get("content", "")

    def batch_complete(self, prompts: List[str], **kwargs) -> List[Dict]:
        return [self.complete(p, **kwargs) for p in prompts]

    def count_tokens(self, text: str) -> int:
        try:
            return self.client.count_tokens(text) if self.client else len(text.split()) * 1.3
        except Exception:
            return int(len(text.split()) * 1.3)
