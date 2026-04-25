# api/payment_gateways/search.py
from decimal import Decimal
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
import logging
logger = logging.getLogger(__name__)

class PaymentSearchEngine:
    def search_transactions(self,query,user=None,filters=None):
        from api.payment_gateways.models.core import GatewayTransaction
        qs=GatewayTransaction.objects.select_related('user')
        if user and not user.is_staff: qs=qs.filter(user=user)
        if query: qs=qs.filter(Q(reference_id__icontains=query)|Q(gateway_reference__icontains=query)|Q(user__email__icontains=query))
        f=filters or {}
        if f.get('status'): qs=qs.filter(status=f['status'])
        if f.get('gateway'): qs=qs.filter(gateway=f['gateway'])
        if f.get('date_from'): qs=qs.filter(created_at__date__gte=f['date_from'])
        if f.get('date_to'): qs=qs.filter(created_at__date__lte=f['date_to'])
        if f.get('amount_min'): qs=qs.filter(amount__gte=Decimal(str(f['amount_min'])))
        if f.get('amount_max'): qs=qs.filter(amount__lte=Decimal(str(f['amount_max'])))
        return qs.order_by('-created_at')

    def search_deposits(self,query,user=None,filters=None):
        from api.payment_gateways.models.deposit import DepositRequest
        qs=DepositRequest.objects.select_related('user')
        if user and not user.is_staff: qs=qs.filter(user=user)
        if query: qs=qs.filter(Q(reference_id__icontains=query)|Q(gateway_ref__icontains=query)|Q(user__email__icontains=query))
        f=filters or {}
        if f.get('status'): qs=qs.filter(status=f['status'])
        if f.get('gateway'): qs=qs.filter(gateway=f['gateway'])
        return qs.order_by('-initiated_at')

    def search_payouts(self,query,user=None,filters=None):
        from api.payment_gateways.models.core import PayoutRequest
        qs=PayoutRequest.objects.select_related('user')
        if user and not user.is_staff: qs=qs.filter(user=user)
        if query: qs=qs.filter(Q(reference_id__icontains=query)|Q(account_number__icontains=query)|Q(user__email__icontains=query))
        f=filters or {}
        if f.get('status'): qs=qs.filter(status=f['status'])
        if f.get('payout_method'): qs=qs.filter(payout_method=f['payout_method'])
        return qs.order_by('-created_at')

    def search_offers(self,query,filters=None,user=None,include_paused=False):
        from api.payment_gateways.offers.models import Offer
        qs=Offer.objects.select_related('advertiser')
        if not include_paused: qs=qs.filter(status='active')
        if user and not user.is_staff:
            qs=qs.filter(Q(is_public=True)|Q(allowed_publishers=user)).exclude(blocked_publishers=user)
        if query: qs=qs.filter(Q(name__icontains=query)|Q(description__icontains=query)|Q(category__icontains=query))
        f=filters or {}
        if f.get('offer_type'): qs=qs.filter(offer_type=f['offer_type'])
        if f.get('category'): qs=qs.filter(category__iexact=f['category'])
        if f.get('min_payout'): qs=qs.filter(publisher_payout__gte=Decimal(str(f['min_payout'])))
        if f.get('country'):
            c=f['country'].upper()
            qs=qs.filter(Q(target_countries=[])|Q(target_countries__contains=[c])).exclude(blocked_countries__contains=[c])
        return qs.order_by('-epc')

    def search_publishers(self,query,filters=None):
        from api.payment_gateways.publisher.models import PublisherProfile
        qs=PublisherProfile.objects.select_related('user')
        if query: qs=qs.filter(Q(user__username__icontains=query)|Q(user__email__icontains=query)|Q(company_name__icontains=query))
        f=filters or {}
        if f.get('status'): qs=qs.filter(status=f['status'])
        if f.get('tier'): qs=qs.filter(tier=f['tier'])
        return qs.order_by('-lifetime_earnings')

    def search_conversions(self,query,user=None,filters=None):
        from api.payment_gateways.tracking.models import Conversion
        qs=Conversion.objects.select_related('publisher','offer')
        if user and not user.is_staff: qs=qs.filter(publisher=user)
        if query: qs=qs.filter(Q(conversion_id__icontains=query)|Q(click_id_raw__icontains=query)|Q(offer__name__icontains=query))
        f=filters or {}
        if f.get('status'): qs=qs.filter(status=f['status'])
        if f.get('country'): qs=qs.filter(country_code=f['country'].upper())
        if f.get('date_from'): qs=qs.filter(created_at__date__gte=f['date_from'])
        return qs.order_by('-created_at')

    def global_search(self,query,user=None,limit=5):
        if not query or len(query)<2: return {}
        results={}
        try: results['transactions']=list(self.search_transactions(query,user).values('id','reference_id','gateway','amount','status','created_at')[:limit])
        except: results['transactions']=[]
        try: results['deposits']=list(self.search_deposits(query,user).values('id','reference_id','gateway','amount','status','initiated_at')[:limit])
        except: results['deposits']=[]
        try: results['payouts']=list(self.search_payouts(query,user).values('id','reference_id','payout_method','amount','status')[:limit])
        except: results['payouts']=[]
        if not user or user.is_staff:
            try: results['offers']=list(self.search_offers(query,user=user).values('id','name','offer_type','publisher_payout','status')[:limit])
            except: results['offers']=[]
        return {k:v for k,v in results.items() if v}

search_engine=PaymentSearchEngine()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_view(request):
    query=request.GET.get('q','').strip()
    search_type=request.GET.get('type','all')
    page=int(request.GET.get('page',1)); page_size=min(int(request.GET.get('page_size',25)),100)
    if len(query)<2: return Response({'success':False,'error':'Query must be at least 2 characters'},status=400)
    engine=PaymentSearchEngine()
    filters={'status':request.GET.get('status'),'gateway':request.GET.get('gateway'),'date_from':request.GET.get('date_from'),'date_to':request.GET.get('date_to'),'amount_min':request.GET.get('amount_min'),'amount_max':request.GET.get('amount_max'),'country':request.GET.get('country')}
    filters={k:v for k,v in filters.items() if v}
    results={}; total=0; offset=(page-1)*page_size
    if search_type in('all','transactions'):
        try: qs=engine.search_transactions(query,request.user,filters); total+=qs.count(); results['transactions']=list(qs.values('id','reference_id','gateway','transaction_type','amount','fee','net_amount','currency','status','created_at')[offset:offset+page_size])
        except: results['transactions']=[]
    if search_type in('all','deposits'):
        try: qs=engine.search_deposits(query,request.user,filters); total+=qs.count(); results['deposits']=list(qs.values('id','reference_id','gateway','amount','status','initiated_at')[offset:offset+page_size])
        except: results['deposits']=[]
    if search_type in('all','offers'):
        try: qs=engine.search_offers(query,filters,user=request.user); total+=qs.count(); results['offers']=list(qs.values('id','name','offer_type','publisher_payout','currency','category','status','epc')[offset:offset+page_size])
        except: results['offers']=[]
    if search_type in('all','conversions'):
        try: qs=engine.search_conversions(query,request.user,filters); total+=qs.count(); results['conversions']=list(qs.values('id','conversion_id','offer__name','payout','currency','status','country_code','created_at')[offset:offset+page_size])
        except: results['conversions']=[]
    return Response({'success':True,'query':query,'type':search_type,'total':total,'page':page,'page_size':page_size,'results':results})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quick_search_view(request):
    query=request.GET.get('q','').strip()
    if len(query)<2: return Response({'results':{}})
    return Response({'success':True,'query':query,'results':PaymentSearchEngine().global_search(query,user=request.user,limit=5)})
