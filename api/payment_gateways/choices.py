# api/payment_gateways/choices.py — All choice constants
from django.db import models

class GatewayName(models.TextChoices):
    BKASH      = 'bkash',      'bKash'
    NAGAD      = 'nagad',      'Nagad'
    SSLCOMMERZ = 'sslcommerz', 'SSLCommerz'
    AMARPAY    = 'amarpay',    'AmarPay'
    UPAY       = 'upay',       'Upay'
    SHURJOPAY  = 'shurjopay',  'ShurjoPay'
    STRIPE     = 'stripe',     'Stripe'
    PAYPAL     = 'paypal',     'PayPal'
    PAYONEER   = 'payoneer',   'Payoneer'
    WIRE       = 'wire',       'Wire Transfer'
    ACH        = 'ach',        'ACH (US Bank)'
    CRYPTO     = 'crypto',     'Cryptocurrency'

class TransactionType(models.TextChoices):
    DEPOSIT    = 'deposit',    'Deposit'
    WITHDRAWAL = 'withdrawal', 'Withdrawal'
    REFUND     = 'refund',     'Refund'
    BONUS      = 'bonus',      'Bonus'
    COMMISSION = 'commission', 'Commission'
    ADJUSTMENT = 'adjustment', 'Adjustment'

class TransactionStatus(models.TextChoices):
    PENDING    = 'pending',    'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED  = 'completed',  'Completed'
    FAILED     = 'failed',     'Failed'
    CANCELLED  = 'cancelled',  'Cancelled'
    REVERSED   = 'reversed',   'Reversed'
    ON_HOLD    = 'on_hold',    'On Hold'

BD_GATEWAYS     = [v.value for v in [GatewayName.BKASH, GatewayName.NAGAD,
                   GatewayName.SSLCOMMERZ, GatewayName.AMARPAY,
                   GatewayName.UPAY, GatewayName.SHURJOPAY]]
GLOBAL_GATEWAYS = [v.value for v in [GatewayName.STRIPE, GatewayName.PAYPAL,
                   GatewayName.PAYONEER, GatewayName.ACH,
                   GatewayName.WIRE, GatewayName.CRYPTO]]
ALL_GATEWAYS    = BD_GATEWAYS + GLOBAL_GATEWAYS
