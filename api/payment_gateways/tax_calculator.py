# api/payment_gateways/tax_calculator.py
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

TAX_RATES={'BD':{'vat':Decimal('0.15'),'withholding':Decimal('0.10')},'US':{'w8_w9':Decimal('0.30')},'EU':{'vat':Decimal('0.20')},'default':{'vat':Decimal('0')}}

class TaxCalculator:
    def calculate(self,amount,country,payment_type='earnings'):
        rates=TAX_RATES.get(country.upper(),TAX_RATES['default'])
        tax_amount=Decimal('0')
        breakdown={}
        if 'vat' in rates and rates['vat']>0:
            vat=(amount*rates['vat']).quantize(Decimal('0.01'))
            tax_amount+=vat; breakdown['vat']=float(vat)
        if 'withholding' in rates and payment_type=='earnings':
            wh=(amount*rates['withholding']).quantize(Decimal('0.01'))
            tax_amount+=wh; breakdown['withholding']=float(wh)
        return {'gross':float(amount),'tax_amount':float(tax_amount),'net_after_tax':float(amount-tax_amount),'breakdown':breakdown,'country':country,'currency':'USD'}
    def get_w8_w9_requirement(self,user,country):
        US_THRESHOLD=Decimal('600')
        if country=='US': return {'required':True,'form':'W-9','reason':'US person earnings > $600'}
        return {'required':False}
    def generate_1099(self,publisher,year):
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum
        from datetime import datetime
        total=Conversion.objects.filter(publisher=publisher,status='approved',created_at__year=year).aggregate(t=Sum('payout'))['t'] or Decimal('0')
        return {'form':'1099-MISC','year':year,'recipient':publisher.email,'amount':float(total),'requires_filing':total>=Decimal('600')}
tax_calculator=TaxCalculator()
