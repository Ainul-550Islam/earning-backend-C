# api/payment_gateways/postback_queue.py
# Reliable postback delivery queue
import logging,json,requests
from django.core.cache import cache
from django.utils import timezone
logger=logging.getLogger(__name__)

class PostbackQueue:
    MAX_RETRIES=5
    RETRY_DELAYS=[30,120,300,900,3600]
    def enqueue(self,postback_url,params,conversion_id,priority=2):
        from api.payment_gateways.integration_system.message_queue import message_queue
        message_queue.enqueue('pg_webhooks',{'url':postback_url,'params':params,'conversion_id':conversion_id,'attempt':0},priority=priority)
    def fire_postback(self,url,params,timeout=5):
        import urllib.parse
        if not url: return {'success':False,'error':'No URL'}
        param_str=urllib.parse.urlencode({k:str(v) for k,v in params.items()})
        full_url=f'{url}{"&" if "?" in url else "?"}{param_str}' if params else url
        try:
            r=requests.get(full_url,timeout=timeout)
            return {'success':True,'status_code':r.status_code,'response':r.text[:200]}
        except Exception as e:
            return {'success':False,'error':str(e)}
    def retry_failed(self,limit=100):
        from api.payment_gateways.integration_system.message_queue import message_queue
        messages=message_queue.get_dlq_messages('pg_webhooks',limit=limit)
        retried=0
        for msg in messages:
            url=msg.get('url',''); params=msg.get('params',{})
            if url:
                result=self.fire_postback(url,params)
                if result['success']: retried+=1
        return {'retried':retried}
postback_queue=PostbackQueue()
