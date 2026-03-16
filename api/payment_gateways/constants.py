## **Api/payment_gateways/constants.py**
# ```python
# Payment Gateway Constants

PAYMENT_GATEWAYS = {
    'BKASH': 'bkash',
    'NAGAD': 'nagad',
    'STRIPE': 'stripe',
    'PAYPAL': 'paypal',
}

TRANSACTION_STATUSES = {
    'PENDING': 'pending',
    'PROCESSING': 'processing',
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'CANCELLED': 'cancelled',
}

MIN_WITHDRAWAL_AMOUNT = 100
MAX_WITHDRAWAL_AMOUNT = 100000

GATEWAY_FEES = {
    'bkash': 0.015,  # 1.5%
    'nagad': 0.012,  # 1.2%
    'stripe': 0.029,  # 2.9%
    'paypal': 0.035,  # 3.5%
}