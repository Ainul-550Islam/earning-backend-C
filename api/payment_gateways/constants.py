# api/payment_gateways/constants.py

PAYMENT_GATEWAYS = {
    'BKASH':      'bkash',
    'NAGAD':      'nagad',
    'SSLCOMMERZ': 'sslcommerz',
    'AMARPAY':    'amarpay',
    'UPAY':       'upay',
    'SHURJOPAY':  'shurjopay',
    'STRIPE':     'stripe',
    'PAYPAL':     'paypal',
    'PAYONEER':   'payoneer',
    'WIRE':       'wire',
    'ACH':        'ach',
    'CRYPTO':     'crypto',
}

BD_GATEWAYS    = ['bkash', 'nagad', 'sslcommerz', 'amarpay', 'upay', 'shurjopay']
GLOBAL_GATEWAYS= ['stripe', 'paypal', 'payoneer', 'ach', 'wire', 'crypto']
ALL_GATEWAYS   = BD_GATEWAYS + GLOBAL_GATEWAYS

TRANSACTION_STATUSES = {
    'PENDING':    'pending',
    'PROCESSING': 'processing',
    'COMPLETED':  'completed',
    'FAILED':     'failed',
    'CANCELLED':  'cancelled',
}

MIN_WITHDRAWAL_AMOUNT = 1       # $1 minimum (like CPAlead)
MAX_WITHDRAWAL_AMOUNT = 100000

GATEWAY_FEES = {
    'bkash':      0.015,   # 1.5%
    'nagad':      0.012,   # 1.2%
    'sslcommerz': 0.020,   # 2.0%
    'amarpay':    0.018,   # 1.8%
    'upay':       0.013,   # 1.3%
    'shurjopay':  0.014,   # 1.4%
    'stripe':     0.029,   # 2.9%
    'paypal':     0.035,   # 3.5%
    'payoneer':   0.020,   # 2.0%
    'wire':       0.010,   # 1.0%
    'ach':        0.008,   # 0.8%
    'crypto':     0.010,   # 1.0%
}

GATEWAY_DISPLAY = {
    'bkash':      {'name': 'bKash',        'color': '#E2136E', 'region': 'BD'},
    'nagad':      {'name': 'Nagad',         'color': '#F7941D', 'region': 'BD'},
    'sslcommerz': {'name': 'SSLCommerz',   'color': '#0072BC', 'region': 'BD'},
    'amarpay':    {'name': 'AmarPay',      'color': '#00AEEF', 'region': 'BD'},
    'upay':       {'name': 'Upay',          'color': '#005BAA', 'region': 'BD'},
    'shurjopay':  {'name': 'ShurjoPay',    'color': '#6A0DAD', 'region': 'BD'},
    'stripe':     {'name': 'Stripe',        'color': '#635BFF', 'region': 'GLOBAL'},
    'paypal':     {'name': 'PayPal',        'color': '#003087', 'region': 'GLOBAL'},
    'payoneer':   {'name': 'Payoneer',      'color': '#FF4800', 'region': 'GLOBAL'},
    'wire':       {'name': 'Wire Transfer', 'color': '#2C3E50', 'region': 'GLOBAL'},
    'ach':        {'name': 'ACH (US Bank)', 'color': '#0A6640', 'region': 'US'},
    'crypto':     {'name': 'Crypto',        'color': '#F7931A', 'region': 'GLOBAL'},
}
