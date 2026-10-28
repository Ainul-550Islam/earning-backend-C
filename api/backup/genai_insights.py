"""
GenAI-Powered Backup Insights
Inspired by: Cohesity GenAI tools, Druva Dru Investigate / Dru Assist,
             Veeam AI Assistant, Rubrik Ruby AI
Provides natural-language Q&A, anomaly explanations, and recovery guidance.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InsightQuery:
    query: str
    context: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InsightResponse:
    query: InsightQuery
    answer: str
    confidence: float          # 0.0 – 1.0
    sources: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query.query,
            "answer": self.answer,
            "confidence": self.confidence,
            "suggested_actions": self.suggested_actions,
            "generated_at": self.generated_at.isoformat(),
        }


class BackupContextBuilder:
    """
    Assembles backup system context (stats, anomalies, alerts)
    to inject into GenAI prompts for grounded, accurate answers.
    """

    def build(self, include_stats: bool = True,
              include_anomalies: bool = True) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}
        if include_stats:
            try:
                from api.backup.interactors import GetBackupStatsInteractor
                ctx["backup_stats"] = GetBackupStatsInteractor().execute()
            except Exception as exc:
                ctx["backup_stats"] = {"error": str(exc)}
        return ctx


class GenAIInsightsEngine:
    """
    GenAI-powered backup insights engine.
    Uses the Anthropic Claude API to answer natural-language questions
    about the backup system, explain anomalies, and recommend actions.
    """

    SYSTEM_PROMPT = """You are an expert backup system analyst with deep knowledge of
enterprise backup platforms (Veeam, Rubrik, Commvault, Cohesity, Acronis).

You have access to real-time backup system context provided in the user message.
Your role is to:
1. Answer questions about backup health, failures, and trends
2. Explain anomalies in plain language
3. Recommend specific recovery or remediation actions
4. Flag security concerns related to ransomware or data integrity

Always be concise, actionable, and specific. Cite backup IDs and metrics when available.
Format your response as JSON with keys: answer, confidence (0-1), suggested_actions (list).
"""

    def __init__(self, model: str = "claude-sonnet-4-20250514",
                 max_tokens: int = 1000):
        self.model = model
        self.max_tokens = max_tokens
        self._context_builder = BackupContextBuilder()
        self._history: List[InsightResponse] = []

    def ask(self, query: str, extra_context: Optional[Dict] = None) -> InsightResponse:
        """Ask a natural-language question about the backup system"""
        ctx = self._context_builder.build()
        if extra_context:
            ctx.update(extra_context)

        insight_query = InsightQuery(query=query, context=ctx)
        user_message = f"""Backup system context:
{json.dumps(ctx, indent=2, default=str)}

Question: {query}

Respond ONLY with valid JSON: {{"answer": "...", "confidence": 0.9, "suggested_actions": ["..."]}}"""

        try:
            import requests
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": self.SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_message}],
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            raw = data["content"][0]["text"]
            parsed = json.loads(raw.strip())

            insight = InsightResponse(
                query=insight_query,
                answer=parsed.get("answer", raw),
                confidence=float(parsed.get("confidence", 0.7)),
                suggested_actions=parsed.get("suggested_actions", []),
                tokens_used=data.get("usage", {}).get("output_tokens", 0),
            )
        except Exception as exc:
            logger.error("GenAI insight failed: %s", exc)
            insight = InsightResponse(
                query=insight_query,
                answer=f"Unable to generate insight: {exc}",
                confidence=0.0,
            )

        self._history.append(insight)
        return insight

    def explain_anomaly(self, anomaly_data: Dict[str, Any]) -> InsightResponse:
        query = (
            f"Explain this backup anomaly and what I should do: "
            f"{json.dumps(anomaly_data)}"
        )
        return self.ask(query, extra_context={"anomaly": anomaly_data})

    def recommend_recovery(self, backup_id: str,
                            incident_type: str = "ransomware") -> InsightResponse:
        query = (
            f"What are the recommended steps to recover backup {backup_id} "
            f"after a {incident_type} incident?"
        )
        return self.ask(query, extra_context={"backup_id": backup_id,
                                               "incident_type": incident_type})

    def summarise_health(self) -> InsightResponse:
        return self.ask(
            "Give me a plain-English summary of the current backup system health "
            "and any concerns I should be aware of."
        )

    def get_history(self, limit: int = 20) -> List[InsightResponse]:
        return self._history[-limit:]
