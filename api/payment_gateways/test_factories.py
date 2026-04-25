# api/payment_gateways/test_factories.py
# Test factories for all models
import factory,secrets
from decimal import Decimal
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model

class UserFactory(DjangoModelFactory):
    class Meta:
        model=get_user_model()
        django_get_or_create=('username',)
    username=factory.Sequence(lambda n:f'testuser{n}')
    email=factory.LazyAttribute(lambda o:f'{o.username}@test.com')
    is_active=True

class GatewayTransactionFactory(DjangoModelFactory):
    class Meta:
        try:
            from api.payment_gateways.models.core import GatewayTransaction
            model=GatewayTransaction
        except: model=None
    user=factory.SubFactory(UserFactory)
    transaction_type='deposit'
    gateway='bkash'
    amount=Decimal('500')
    fee=Decimal('7.5')
    net_amount=Decimal('492.5')
    currency='BDT'
    status='completed'
    reference_id=factory.LazyFunction(lambda:f'TEST-{secrets.token_hex(6).upper()}')

class DepositRequestFactory(DjangoModelFactory):
    class Meta:
        try:
            from api.payment_gateways.models.deposit import DepositRequest
            model=DepositRequest
        except: model=None
    user=factory.SubFactory(UserFactory)
    gateway='bkash'
    amount=Decimal('500')
    fee=Decimal('7.5')
    net_amount=Decimal('492.5')
    currency='BDT'
    status='completed'
    reference_id=factory.LazyFunction(lambda:f'DEP-TEST-{secrets.token_hex(6).upper()}')
