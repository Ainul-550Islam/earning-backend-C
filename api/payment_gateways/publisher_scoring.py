# api/payment_gateways/publisher_scoring.py
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class PublisherScoringEngine:
    def calculate_score(self,publisher):
        from api.payment_gateways.tracking.models import Conversion,Click
        from django.db.models import Count,Avg,Sum
        from django.utils import timezone
        from datetime import timedelta
        since=timezone.now()-timedelta(days=30)
        clicks=Click.objects.filter(publisher=publisher,created_at__gte=since)
        convs=Conversion.objects.filter(publisher=publisher,status='approved',created_at__gte=since)
        total_clicks=max(clicks.count(),1)
        fraud_clicks=clicks.filter(is_fraud=True).count()
        bot_clicks=clicks.filter(is_bot=True).count()
        conv_count=convs.count()
        reversal_count=Conversion.objects.filter(publisher=publisher,status='reversed',created_at__gte=since).count()
        fraud_rate=fraud_clicks/total_clicks
        cr=conv_count/total_clicks
        reversal_rate=reversal_count/max(conv_count,1)
        score=100.0
        score-=fraud_rate*50
        score-=bot_clicks/total_clicks*30
        score-=reversal_rate*40
        if cr>0.001: score+=min(cr*1000,20)
        score=max(0,min(100,score))
        tier='bronze'
        if score>=80: tier='gold'
        elif score>=60: tier='silver'
        return {'score':round(score,1),'tier':tier,'fraud_rate':round(fraud_rate*100,2),'cr':round(cr*100,4),'reversal_rate':round(reversal_rate*100,2),'clicks_30d':total_clicks,'conversions_30d':conv_count}
    def update_all_scores(self):
        from api.payment_gateways.publisher.models import PublisherProfile
        updated=0
        for pub in PublisherProfile.objects.filter(status='active').select_related('user')[:500]:
            try:
                s=self.calculate_score(pub.user)
                PublisherProfile.objects.filter(id=pub.id).update(quality_score=Decimal(str(s['score'])),tier=s['tier'])
                updated+=1
            except: pass
        return {'updated':updated}
publisher_scoring=PublisherScoringEngine()
