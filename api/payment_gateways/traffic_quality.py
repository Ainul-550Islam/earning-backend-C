# api/payment_gateways/traffic_quality.py
# Traffic quality scoring
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class TrafficQualityScorer:
    def score_click(self,click):
        score=100
        reasons=[]
        if click.is_bot: return 0,['Bot traffic detected']
        if click.is_fraud: score-=80; reasons.append('Fraud flag')
        ua=(click.user_agent or '').lower()
        if any(p in ua for p in ['bot','crawler','spider','wget','curl']): score-=90; reasons.append('Bot user agent')
        if not click.country_code: score-=10; reasons.append('Unknown country')
        from api.payment_gateways.services.GeoPricingEngine import GeoPricingEngine
        tier=GeoPricingEngine().get_country_tier(click.country_code or '')
        if tier==1: score+=5
        elif tier==3: score-=5
        return max(0,min(100,score)), reasons
    def get_publisher_traffic_quality(self,publisher,days=30):
        from api.payment_gateways.tracking.models import Click
        from django.db.models import Count,Avg
        from django.utils import timezone
        from datetime import timedelta
        since=timezone.now()-timedelta(days=days)
        qs=Click.objects.filter(publisher=publisher,created_at__gte=since)
        total=qs.count()
        if not total: return {'score':0,'total_clicks':0}
        fraud=qs.filter(is_fraud=True).count()
        bots=qs.filter(is_bot=True).count()
        converted=qs.filter(is_converted=True).count()
        quality_score=100-((fraud+bots)/total*100)
        return {'score':round(max(0,quality_score),1),'total_clicks':total,'fraud_clicks':fraud,'bot_clicks':bots,'converted_clicks':converted,'fraud_rate':round(fraud/total*100,2),'conversion_rate':round(converted/total*100,4)}
traffic_quality=TrafficQualityScorer()
