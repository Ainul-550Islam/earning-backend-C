# api/payment_gateways/ab_testing.py
# A/B testing framework
import logging,random,hashlib
from django.core.cache import cache
logger=logging.getLogger(__name__)

class ABTestManager:
    def get_variant(self,test_name,user_id,variants=None,weights=None):
        if not variants: variants=['control','treatment']
        if not weights: weights=[50]*(len(variants)-1)+[100-50*(len(variants)-1)]
        cache_key=f'ab:{test_name}:{user_id}'
        cached=cache.get(cache_key)
        if cached: return cached
        seed=int(hashlib.md5(f'{test_name}:{user_id}'.encode()).hexdigest(),16)%100
        cumulative=0
        selected=variants[-1]
        for v,w in zip(variants,weights):
            cumulative+=w
            if seed<cumulative: selected=v; break
        cache.set(cache_key,selected,86400*7)
        return selected
    def record_conversion(self,test_name,variant,metric='conversion'):
        key=f'ab:conv:{test_name}:{variant}:{metric}'
        from django_redis import get_redis_connection
        try:
            conn=get_redis_connection('default')
            conn.incr(key); conn.expire(key,86400*30)
        except: cache.set(key,(cache.get(key,0) or 0)+1,86400*30)
    def get_results(self,test_name,variants=None):
        if not variants: variants=['control','treatment']
        results={}
        for v in variants:
            convs=cache.get(f'ab:conv:{test_name}:{v}:conversion') or 0
            imps=cache.get(f'ab:conv:{test_name}:{v}:impression') or 0
            results[v]={'conversions':convs,'impressions':imps,'cr':round(convs/max(imps,1)*100,2)}
        return results
ab_test_manager=ABTestManager()
