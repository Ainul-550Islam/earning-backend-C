# api/payment_gateways/mock_gateways.py
# Mock gateway services for testing
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class MockGatewayBase:
    gateway_name='mock'
    def process_deposit(self,user,amount,**kwargs):
        return {'success':True,'payment_url':f'https://mock.test/pay/{self.gateway_name}','payment_id':f'mock_{self.gateway_name}_test_123','session_key':'mock_session_key','amount':float(amount),'currency':'BDT'}
    def verify_payment(self,session_id,**kwargs):
        return {'status':'completed','amount':0,'gateway_ref':f'mock_ref_{session_id}'}
    def process_withdrawal(self,user,amount,payment_method,**kwargs):
        return {'success':True,'gateway_ref':f'mock_payout_{amount}','status':'completed','amount':float(amount)}
    def process_refund(self,transaction_id,amount,**kwargs):
        return {'success':True,'refund_id':f'mock_refund_{transaction_id}','amount':float(amount)}
    def validate_amount(self,amount): pass
    def get_fee(self,amount): return (amount*Decimal('0.015')).quantize(Decimal('0.01'))

class MockBkashService(MockGatewayBase):
    gateway_name='bkash'
    def process_deposit(self,user,amount,**kwargs):
        r=super().process_deposit(user,amount,**kwargs)
        r['payment_url']=f'https://sandbox.bkash.com/checkout/mock?amount={amount}'
        return r

class MockStripeService(MockGatewayBase):
    gateway_name='stripe'
    def process_deposit(self,user,amount,**kwargs):
        r=super().process_deposit(user,amount,**kwargs)
        r['payment_url']=f'https://checkout.stripe.com/mock/pay/cs_test_abc123'
        r['currency']='USD'
        return r

class MockPayPalService(MockGatewayBase):
    gateway_name='paypal'

def get_mock_service(gateway):
    mocks={'bkash':MockBkashService,'nagad':MockGatewayBase,'stripe':MockStripeService,'paypal':MockPayPalService}
    cls=mocks.get(gateway,MockGatewayBase)
    svc=cls(); svc.gateway_name=gateway; return svc
