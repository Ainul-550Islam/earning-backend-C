# api/payment_gateways/signals_kb.py
from django.dispatch import Signal, receiver
from django.utils import timezone
import logging
logger=logging.getLogger(__name__)

gateway_pattern_detected=Signal()
gateway_error_classified=Signal()
publisher_first_conversion=Signal()
publisher_milestone_reached=Signal()
new_fraud_pattern=Signal()
fraud_rule_triggered=Signal()
postback_failure_pattern=Signal()
error_threshold_crossed=Signal()
offer_epc_changed=Signal()

try:
    from django.db import models
    from core.models import TimeStampedModel
    class KnowledgeBaseEntry(TimeStampedModel):
        CATEGORIES=(('gateway_error','Gateway Error'),('fraud_pattern','Fraud Pattern'),('publisher_guide','Publisher Guide'),('advertiser_guide','Advertiser Guide'),('offer_insight','Offer Insight'),('system_alert','System Alert'),('postback_help','Postback Help'),('payment_help','Payment Help'),('general','General'))
        SEVERITY=(('info','Info'),('tip','Tip'),('warning','Warning'),('critical','Critical'))
        title=models.CharField(max_length=300,db_index=True)
        slug=models.SlugField(max_length=320,unique=True,blank=True)
        category=models.CharField(max_length=20,choices=CATEGORIES,default='general')
        severity=models.CharField(max_length=10,choices=SEVERITY,default='info')
        content=models.TextField()
        summary=models.CharField(max_length=500,blank=True)
        tags=models.JSONField(default=list,blank=True)
        related_gateway=models.CharField(max_length=20,blank=True,db_index=True)
        auto_generated=models.BooleanField(default=False)
        source_signal=models.CharField(max_length=100,blank=True)
        view_count=models.IntegerField(default=0)
        is_published=models.BooleanField(default=True)
        expires_at=models.DateTimeField(null=True,blank=True)
        class Meta:
            app_label='payment_gateways'; verbose_name='Knowledge Base Entry'; ordering=['-created_at']
        def __str__(self): return f'[{self.category}] {self.title}'
        def save(self,*a,**kw):
            if not self.slug:
                from django.utils.text import slugify; import time
                self.slug=f'{slugify(self.title)[:300]}-{int(time.time())}'
            if not self.summary and self.content:
                c=self.content.replace('#','').replace('*','').strip(); self.summary=c[:150]+('...' if len(c)>150 else '')
            super().save(*a,**kw)
        def increment_view(self): KnowledgeBaseEntry.objects.filter(id=self.id).update(view_count=models.F('view_count')+1)
except ImportError:
    class KnowledgeBaseEntry: pass

@receiver(gateway_error_classified)
def handle_gateway_error_kb(sender,gateway,error_code,error_class,suggestion='',**kw):
    title=f'{gateway.upper()} Error: {error_code} — {error_class}'
    if not _kb_exists(title):
        _create_kb_entry(title=title,category='gateway_error',severity='warning',
            content=f'## Error: {error_code}\n**Gateway:** {gateway.upper()}\n**Classification:** {error_class}\n\n### Suggested Resolution\n{suggestion or "Contact gateway support."}',
            tags=[gateway,error_code,'error'],gateway=gateway,source='gateway_error_classified')

@receiver(new_fraud_pattern)
def handle_fraud_pattern_kb(sender,pattern_type,description,affected_gateways=None,**kw):
    title=f'Fraud Pattern Detected: {pattern_type}'
    if not _kb_exists(title):
        _create_kb_entry(title=title,category='fraud_pattern',severity='critical',
            content=f'## Fraud Pattern: {pattern_type}\n**Description:** {description}\n**Affected Gateways:** {", ".join(affected_gateways or ["All"])}',
            tags=['fraud','security',pattern_type],source='new_fraud_pattern')

@receiver(publisher_first_conversion)
def handle_first_conversion_kb(sender,publisher,offer,amount,**kw):
    logger.info(f'Publisher first conversion: user={publisher.id} amount={amount}')
    try:
        from api.payment_gateways.publisher.models import PublisherProfile
        PublisherProfile.objects.filter(user=publisher).update(first_conversion_at=timezone.now())
    except: pass
    publisher_milestone_reached.send(sender=sender,publisher=publisher,milestone_type='first_conversion',value=float(amount))

@receiver(publisher_milestone_reached)
def handle_publisher_milestone(sender,publisher,milestone_type,value,**kw):
    MSGS={'first_conversion':('🎉 First Conversion!',f'You earned ${value:.2f}!'),
          'earnings_100':('💰 $100 milestone!',f'Total: ${value:.2f}'),
          'earnings_1000':('🏆 $1,000 milestone!',f'Total: ${value:.2f}')}
    msg=MSGS.get(milestone_type,('🎯 Milestone!',str(value)))
    try:
        from api.payment_gateways.integrations_adapters.NotificationAdapter import NotificationAdapter
        NotificationAdapter()._fallback_email(publisher,subject=msg[0],message=msg[1])
    except: pass

def search_kb(query,category=None,gateway=None,limit=10):
    try:
        from django.db.models import Q
        qs=KnowledgeBaseEntry.objects.filter(is_published=True)
        qs=qs.filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now()))
        if category: qs=qs.filter(category=category)
        if gateway: qs=qs.filter(related_gateway=gateway)
        if query: qs=qs.filter(Q(title__icontains=query)|Q(content__icontains=query)|Q(summary__icontains=query))
        return list(qs.values('id','title','slug','category','severity','summary','tags','related_gateway','view_count')[:limit])
    except Exception as e:
        logger.debug(f'KB search failed: {e}'); return []

def emit_gateway_error(gateway,error_code,error_class,suggestion=''):
    gateway_error_classified.send(sender=None,gateway=gateway,error_code=error_code,error_class=error_class,suggestion=suggestion)

def emit_first_conversion(publisher,offer,amount):
    try:
        from api.payment_gateways.tracking.models import Conversion
        if Conversion.objects.filter(publisher=publisher,status='approved').count()==1:
            publisher_first_conversion.send(sender=None,publisher=publisher,offer=offer,amount=amount)
    except: pass

def emit_fraud_pattern(pattern_type,description,affected_gateways=None):
    new_fraud_pattern.send(sender=None,pattern_type=pattern_type,description=description,affected_gateways=affected_gateways or [])

def _kb_exists(title):
    try: return KnowledgeBaseEntry.objects.filter(title=title).exists()
    except: return False

def _create_kb_entry(title,content,category='general',severity='info',tags=None,gateway='',source='',expires_hours=None):
    try:
        expires_at=None
        if expires_hours:
            from datetime import timedelta; expires_at=timezone.now()+timedelta(hours=expires_hours)
        KnowledgeBaseEntry.objects.create(title=title[:300],category=category,severity=severity,content=content,tags=tags or [],related_gateway=gateway,auto_generated=True,source_signal=source,expires_at=expires_at,is_published=True)
        return True
    except Exception as e:
        logger.debug(f'KB entry creation failed: {e}'); return False
