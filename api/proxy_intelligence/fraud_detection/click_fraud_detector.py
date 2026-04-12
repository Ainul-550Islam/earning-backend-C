"""Click Fraud Detector — detects fake/bot ad clicks."""
import logging
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger(__name__)

class ClickFraudDetector:
    def __init__(self, ip_address: str, user=None, tenant=None):
        self.ip_address = ip_address
        self.user = user
        self.tenant = tenant

    def analyze_click(self, target_url: str = '', user_agent: str = '',
                      referrer: str = '', session_id: str = '',
                      time_on_page: float = None) -> dict:
        flags = []
        score = 0

        # Check click velocity
        vel_key = f"pi:click_vel:{self.ip_address}"
        click_count = cache.get(vel_key, 0) + 1
        cache.set(vel_key, click_count, 60)

        if click_count > 10:
            flags.append(f'high_click_velocity:{click_count}/min')
            score += 30

        # Bot UA check
        bot_keywords = ['bot','curl','wget','python','scrapy','selenium','headless']
        if any(kw in user_agent.lower() for kw in bot_keywords):
            flags.append('bot_user_agent')
            score += 40

        # Too fast (< 1s on page)
        if time_on_page is not None and 0 < time_on_page < 1.0:
            flags.append('too_fast_click')
            score += 20

        # No referrer for ad click is suspicious
        if not referrer and target_url:
            flags.append('missing_referrer')
            score += 10

        is_fraud = score >= 40
        self._save(target_url, user_agent, referrer, session_id,
                   time_on_page, click_count, score, is_fraud)

        return {
            'ip_address': self.ip_address,
            'is_click_fraud': is_fraud,
            'fraud_score': min(score, 100),
            'flags': flags,
            'click_frequency': click_count,
        }

    def _save(self, url, ua, ref, sid, top, freq, score, is_fraud):
        try:
            from ..models import ClickFraudRecord
            ClickFraudRecord.objects.create(
                ip_address=self.ip_address, user=self.user,
                target_url=url[:500] if url else '',
                user_agent=ua, referrer=ref[:500] if ref else '',
                session_id=sid, time_on_page=top,
                click_frequency=freq, fraud_score=score,
                is_bot=('bot_user_agent' in str(score)),
                tenant=self.tenant,
            )
        except Exception as e:
            logger.debug(f"ClickFraudRecord save failed: {e}")
