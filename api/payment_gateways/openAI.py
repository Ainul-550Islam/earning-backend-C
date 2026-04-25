# api/payment_gateways/openAI.py
# OpenAI-powered payment intelligence
import logging, json
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
logger=logging.getLogger(__name__)
GPT_MODEL='gpt-4o-mini'; MAX_TOKENS=1500; CACHE_TTL=3600
_client=None

def _get_client():
    global _client
    if _client is None:
        import openai
        api_key=getattr(settings,'OPENAI_API_KEY','')
        if not api_key: raise ValueError('OPENAI_API_KEY not set')
        _client=openai.OpenAI(api_key=api_key)
    return _client

def _call_gpt(system_prompt,user_message,temperature=0.1,cache_key=None,cache_ttl=CACHE_TTL):
    if cache_key:
        cached=cache.get(cache_key)
        if cached: return cached
    try:
        r=_get_client().chat.completions.create(model=GPT_MODEL,max_tokens=MAX_TOKENS,temperature=temperature,
            messages=[{'role':'system','content':system_prompt},{'role':'user','content':user_message}])
        result=r.choices[0].message.content.strip()
        if cache_key and result: cache.set(cache_key,result,cache_ttl)
        return result
    except Exception as e: logger.error(f'OpenAI failed: {e}'); raise

def _call_gpt_json(system_prompt,user_message):
    try:
        r=_get_client().chat.completions.create(model=GPT_MODEL,max_tokens=MAX_TOKENS,temperature=0.1,
            response_format={'type':'json_object'},
            messages=[{'role':'system','content':system_prompt+'\nAlways respond with valid JSON only.'},{'role':'user','content':user_message}])
        return json.loads(r.choices[0].message.content.strip())
    except json.JSONDecodeError: return {}
    except Exception as e: logger.error(f'OpenAI JSON failed: {e}'); return {}

def ai_fraud_risk_score(user,amount,gateway,ip,user_agent,transaction_history=None):
    try:
        from api.ai_engine.services import AIFraudService
        return AIFraudService().predict_fraud(user=user,amount=float(amount),gateway=gateway,ip=ip,user_agent=user_agent)
    except ImportError: pass
    try:
        result=_call_gpt_json(
            'You are a payment fraud detection AI. Return JSON: risk_score(0-100), risk_level(low/medium/high/critical), action(allow/flag/verify/block), reasons(array), confidence(0-1)',
            f'User ID:{user.id} Account age:{_account_age(user)}days Amount:${float(amount):.2f} Gateway:{gateway} IP:{_anon_ip(ip)} UA:{user_agent[:80]}')
        return {'risk_score':result.get('risk_score',0),'risk_level':result.get('risk_level','low'),'action':result.get('action','allow'),'reasons':result.get('reasons',[]),'confidence':result.get('confidence',0.5),'source':'openai'}
    except Exception as e:
        logger.warning(f'AI fraud scoring failed: {e}')
        return {'risk_score':0,'risk_level':'low','action':'allow','reasons':[],'confidence':0.0}

def ai_recommend_offers(publisher,country,device,traffic_sources=None,limit=10):
    try:
        from api.ai_engine.services import AIOfferService
        return AIOfferService().recommend(publisher=publisher,country=country,device=device,limit=limit)
    except ImportError: pass
    try:
        from api.payment_gateways.offers.models import Offer
        from django.db.models import Q
        qs=Offer.objects.filter(status='active').filter(Q(is_public=True)|Q(allowed_publishers=publisher)).exclude(blocked_publishers=publisher)
        if country: qs=qs.filter(Q(target_countries=[])|Q(target_countries__contains=[country])).exclude(blocked_countries__contains=[country])
        return list(qs.order_by('-epc')[:limit])
    except Exception: return []

def ai_support_response(subject,description,category='general',publisher_info=None):
    try:
        from api.payment_gateways.signals_kb import search_kb
        kb=search_kb(f'{subject} {description[:100]}',limit=3)
        kb_ctx='\n'.join([f'- {e["title"]}: {e["summary"]}' for e in kb]) if kb else ''
        return _call_gpt(
            'You are a helpful payment network support agent. Write professional, concise (max 200 words) responses. Sign as "Support Team".',
            f'Subject:{subject}\nCategory:{category}\nDescription:{description[:400]}\n{f"KB:{kb_ctx}" if kb_ctx else ""}',
            temperature=0.3,cache_key=f'ai_support:{hash(subject+description[:80])}',cache_ttl=1800)
    except Exception:
        return f'Thank you for contacting us regarding "{subject}". Our support team will review within 24 hours.\n\nBest regards,\nSupport Team'

def ai_detect_payout_anomaly(publisher,requested_amount,recent_earnings=None):
    if not recent_earnings: recent_earnings=[]
    if not recent_earnings or sum(recent_earnings)==0: return {'is_anomalous':False,'risk':'low','reason':'','recommendation':''}
    avg_daily=sum(recent_earnings)/len(recent_earnings); ratio=float(requested_amount)/max(avg_daily,0.01)
    if ratio<5: return {'is_anomalous':False,'risk':'low','reason':'','recommendation':'Normal request.'}
    try:
        result=_call_gpt_json('You are a payment fraud analyst. Analyze payout anomaly. Return JSON: is_anomalous(bool), risk(low/medium/high), reason(str), recommendation(str)',
            f'Publisher:{publisher.id} Requested:${float(requested_amount):.2f} Last 7d earnings:{[f"${e:.2f}" for e in recent_earnings]} Avg daily:${avg_daily:.2f} ({ratio:.1f}x average)')
        return result
    except: return {'is_anomalous':ratio>20,'risk':'high' if ratio>20 else 'medium','reason':f'Payout is {ratio:.1f}x average daily earnings','recommendation':'Manual review recommended.'}

def ai_generate_offer_description(offer_name,offer_type,target_countries,payout,category=''):
    try:
        result=_call_gpt_json('You are a CPA marketing copywriter. Return JSON: short_desc, description, call_to_action, keywords(array)',
            f'Name:{offer_name} Type:{offer_type} Category:{category} GEOs:{", ".join(target_countries[:5])} Payout:${payout:.2f}')
        return {'short_desc':result.get('short_desc',f'{offer_name} — Earn ${payout:.2f}'),'description':result.get('description',f'Earn ${payout:.2f} per {offer_type}.'),'call_to_action':result.get('call_to_action','Get Link'),'keywords':result.get('keywords',[offer_type,category or 'offer'])}
    except: return {'short_desc':f'{offer_name} — Earn ${payout:.2f}','description':f'Promote {offer_name}.','call_to_action':'Get Link','keywords':[offer_type]}

def ai_publisher_chat(message,publisher,conversation_history=None):
    try:
        balance=float(getattr(publisher,'balance',0) or 0)
        messages=[{'role':'system','content':f'You are a helpful CPA affiliate network assistant. Publisher: {publisher.username}, balance: ${balance:.2f}. Be concise (max 150 words).'}]
        if conversation_history: messages.extend(conversation_history[-10:])
        messages.append({'role':'user','content':message})
        r=_get_client().chat.completions.create(model=GPT_MODEL,max_tokens=300,temperature=0.5,messages=messages)
        return r.choices[0].message.content.strip()
    except: return 'For account-specific questions, please open a support ticket.'

def is_openai_available():
    try: return bool(getattr(settings,'OPENAI_API_KEY',''))
    except: return False

def _account_age(user):
    try:
        from django.utils import timezone; return (timezone.now()-user.date_joined).days
    except: return 0

def _anon_ip(ip):
    if not ip: return '0.0.0.0'
    parts=ip.split('.')
    return f'{parts[0]}.{parts[1]}.*.*' if len(parts)==4 else ip[:10]+'***'
