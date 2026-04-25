# api/payment_gateways/seed_data.py
# Seed/fixture data generators
import logging
logger=logging.getLogger(__name__)

def seed_gateways():
    from api.payment_gateways.models.core import PaymentGateway
    from decimal import Decimal
    GATEWAYS=[
        {'name':'bkash','display_name':'bKash','status':'active','region':'BD','color_code':'#E2136E','sort_order':1,'minimum_amount':Decimal('10'),'maximum_amount':Decimal('50000'),'transaction_fee_percentage':Decimal('1.5'),'supports_deposit':True,'supports_withdrawal':True},
        {'name':'nagad','display_name':'Nagad','status':'active','region':'BD','color_code':'#F7941D','sort_order':2,'minimum_amount':Decimal('10'),'maximum_amount':Decimal('50000'),'transaction_fee_percentage':Decimal('1.2'),'supports_deposit':True,'supports_withdrawal':True},
        {'name':'sslcommerz','display_name':'SSLCommerz','status':'active','region':'BD','color_code':'#0072BC','sort_order':3,'minimum_amount':Decimal('10'),'maximum_amount':Decimal('500000'),'transaction_fee_percentage':Decimal('2.5'),'supports_deposit':True,'supports_withdrawal':False},
        {'name':'stripe','display_name':'Stripe','status':'active','region':'GLOBAL','color_code':'#635BFF','sort_order':7,'minimum_amount':Decimal('0.50'),'maximum_amount':Decimal('999999'),'transaction_fee_percentage':Decimal('2.9'),'supports_deposit':True,'supports_withdrawal':True},
        {'name':'paypal','display_name':'PayPal','status':'active','region':'GLOBAL','color_code':'#003087','sort_order':8,'minimum_amount':Decimal('1'),'maximum_amount':Decimal('999999'),'transaction_fee_percentage':Decimal('3.5'),'supports_deposit':True,'supports_withdrawal':True},
        {'name':'crypto','display_name':'Crypto (USDT/BTC/ETH)','status':'active','region':'GLOBAL','color_code':'#F7931A','sort_order':12,'minimum_amount':Decimal('10'),'maximum_amount':Decimal('9999999'),'transaction_fee_percentage':Decimal('1.0'),'supports_deposit':True,'supports_withdrawal':True},
    ]
    created=0
    for gw_data in GATEWAYS:
        PaymentGateway.objects.get_or_create(name=gw_data['name'],defaults=gw_data)
        created+=1
    return {'seeded':created}

def seed_currencies():
    from api.payment_gateways.models.core import Currency
    from decimal import Decimal
    CURRENCIES=[('BDT','Bangladeshi Taka','৳',Decimal('110.5')),('USD','US Dollar','$',Decimal('1.0')),('EUR','Euro','€',Decimal('0.92')),('GBP','British Pound','£',Decimal('0.79')),('USDT','Tether USD','₮',Decimal('1.0')),('BTC','Bitcoin','₿',Decimal('0.0000155')),('ETH','Ethereum','Ξ',Decimal('0.00032'))]
    created=0
    for code,name,symbol,rate in CURRENCIES:
        Currency.objects.get_or_create(code=code,defaults={'name':name,'symbol':symbol,'exchange_rate':rate,'is_active':True})
        created+=1
    return {'seeded':created}
