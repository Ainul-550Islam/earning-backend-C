"""
api/support/cpa/account_tier_sla.py
FILE 6 — Account Tier-Based SLA

VIP publishers get faster support।
Tier → SLA automatically applied।
"""
import logging
logger = logging.getLogger(__name__)

TIER_SLA_MAP = {
    'vip':        {'first_response': 1,  'resolution': 4,   'priority': 'urgent'},
    'gold':       {'first_response': 2,  'resolution': 8,   'priority': 'high'},
    'silver':     {'first_response': 4,  'resolution': 24,  'priority': 'medium'},
    'standard':   {'first_response': 8,  'resolution': 48,  'priority': 'medium'},
    'new':        {'first_response': 24, 'resolution': 72,  'priority': 'low'},
    'enterprise': {'first_response': 1,  'resolution': 4,   'priority': 'urgent'},
    'premium':    {'first_response': 2,  'resolution': 8,   'priority': 'high'},
}

class TierSLAManager:
    def get_sla_for_user(self, user) -> dict:
        try:
            from api.support.cpa.publisher_portal import publisher_portal
            tier_data = publisher_portal.get_publisher_tier(user)
            tier      = tier_data.get('tier', 'standard')
        except Exception:
            tier = 'standard'
        return {**TIER_SLA_MAP.get(tier, TIER_SLA_MAP['standard']), 'tier': tier}

    def apply_tier_sla(self, ticket) -> dict:
        """Ticket create হলে tier SLA apply করো"""
        sla_data = self.get_sla_for_user(ticket.user)

        # Override priority based on tier
        priority_map = {'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}
        current_p    = priority_map.get(ticket.priority, 2)
        tier_p       = priority_map.get(sla_data['priority'], 2)

        if tier_p > current_p:
            ticket.priority = sla_data['priority']
            ticket.save(update_fields=['priority'])
            logger.info(f'Ticket {ticket.ticket_id} priority upgraded to {sla_data["priority"]} (tier: {sla_data["tier"]})')

        # Setup SLA
        try:
            from api.support.sla.advanced_sla_engine import advanced_sla_engine
            advanced_sla_engine.setup_ticket_sla(ticket)
        except Exception as e:
            logger.warning(f'Tier SLA setup failed: {e}')

        return sla_data

    def get_tier_badge(self, tier: str) -> str:
        badges = {'vip':'⭐ VIP','gold':'🥇 Gold','silver':'🥈 Silver','standard':'🎫 Standard','new':'🆕 New','enterprise':'💎 Enterprise'}
        return badges.get(tier, tier.title())

tier_sla_manager = TierSLAManager()