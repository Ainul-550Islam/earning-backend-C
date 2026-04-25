# api/payment_gateways/click_fraud_ml.py
# ML-based click fraud detection
import logging
from decimal import Decimal
logger=logging.getLogger(__name__)

class ClickFraudMLDetector:
    FEATURES=['hour_of_day','clicks_per_hour','conversion_rate','country_tier','device_type','ip_reputation','fingerprint_score','time_on_site']
    def predict(self,click_data):
        try:
            from api.ai_engine.services import FraudMLService
            return FraudMLService().predict_click_fraud(click_data)
        except ImportError: pass
        score=self._heuristic_score(click_data)
        return {'is_fraud':score>=70,'confidence':score/100,'score':score,'method':'heuristic'}
    def _heuristic_score(self,data):
        score=0
        ip=data.get('ip','')
        if data.get('is_vpn'): score+=30
        if data.get('is_tor'): score+=50
        if data.get('is_bot'): score+=80
        if data.get('clicks_per_hour',0)>100: score+=20
        if data.get('conversion_rate',1)>0.5: score+=15
        if data.get('country_tier',2)==3 and data.get('conversion_rate',0)>0.3: score+=10
        return min(100,score)
    def bulk_analyze(self,clicks):
        results=[]; fraud=0
        for click in clicks:
            r=self.predict({'ip':click.ip_address,'is_bot':click.is_bot,'is_fraud':click.is_fraud})
            if r['is_fraud']:
                fraud+=1
                results.append({'click_id':click.click_id,'score':r['score']})
        return {'analyzed':len(clicks),'fraud_detected':fraud,'results':results}
click_fraud_detector=ClickFraudMLDetector()
