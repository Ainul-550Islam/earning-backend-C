# api/payment_gateways/factories.py
# Test factories for all payment_gateways models

import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
import time, secrets


class PaymentGatewayFactory(DjangoModelFactory):
    class Meta:
        model  = 'payment_gateways.PaymentGateway'
        django_get_or_create = ('name',)
    name              = 'bkash'
    display_name      = 'bKash'
    status            = 'active'
    is_test_mode      = True
    transaction_fee_percentage = Decimal('1.5')
    minimum_amount    = Decimal('10')
    maximum_amount    = Decimal('50000')
    supports_deposit  = True
    supports_withdrawal = True


class GatewayTransactionFactory(DjangoModelFactory):
    class Meta:
        model = 'payment_gateways.GatewayTransaction'
    user             = factory.SubFactory('api.users.tests.factories.UserFactory')
    transaction_type = 'deposit'
    gateway          = 'bkash'
    amount           = Decimal('500')
    fee              = Decimal('7.5')
    net_amount       = Decimal('492.5')
    currency         = 'BDT'
    status           = 'completed'
    reference_id     = factory.LazyFunction(lambda: f'TEST-{secrets.token_hex(6).upper()}')


class DepositRequestFactory(DjangoModelFactory):
    class Meta:
        model = 'payment_gateways.DepositRequest'
    user         = factory.SubFactory('api.users.tests.factories.UserFactory')
    gateway      = 'bkash'
    amount       = Decimal('500')
    fee          = Decimal('7.5')
    net_amount   = Decimal('492.5')
    currency     = 'BDT'
    status       = 'completed'
    reference_id = factory.LazyFunction(lambda: f'DEP-TEST-{secrets.token_hex(6).upper()}')


class PayoutRequestFactory(DjangoModelFactory):
    class Meta:
        model = 'payment_gateways.PayoutRequest'
    user           = factory.SubFactory('api.users.tests.factories.UserFactory')
    amount         = Decimal('1000')
    fee            = Decimal('15')
    net_amount     = Decimal('985')
    payout_method  = 'bkash'
    account_number = '01712345678'
    status         = 'pending'
    reference_id   = factory.LazyFunction(lambda: f'PAY-TEST-{secrets.token_hex(6).upper()}')
