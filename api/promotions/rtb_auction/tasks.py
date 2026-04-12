# =============================================================================
# promotions/rtb_auction/tasks.py
# RTB Auction Celery Task — runs every minute
# CPAlead: "Real-time bidding system forces advertisers to fight for your traffic"
# =============================================================================
from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=0)
def run_rtb_auction(self):
    """
    Run RTB auction every minute.
    In production: match pending traffic slots with highest bidder.
    """
    from api.promotions.models import Campaign
    from django.db.models import Max
    
    # Get top bidding active campaigns
    top_campaigns = Campaign.objects.filter(
        status='active',
        total_budget__gt=0,
    ).order_by('-per_task_reward')[:10]
    
    results = []
    for c in top_campaigns:
        results.append({
            'campaign_id': c.id,
            'bid': float(c.per_task_reward),
        })
    
    logger.debug(f'RTB auction ran: {len(results)} campaigns in auction')
    return {'auction_size': len(results), 'timestamp': __import__('time').time()}
