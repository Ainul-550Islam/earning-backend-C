# api/payment_gateways/services/PaymentFactory.py
# UPDATED: All 12 payment methods registered

from .BkashService      import BkashService
from .NagadService      import NagadService
from .SSLCommerzService import SSLCommerzService
from .AmarPayService    import AmarPayService
from .UpayService       import UpayService
from .ShurjoPayService  import ShurjoPayService
from .StripeService     import StripeService
from .PayPalService     import PayPalService
from .WireTransferService import WireTransferService
from .ACHService        import ACHService
from .CryptoService     import CryptoService
from .PayoneerService   import PayoneerService


class PaymentFactory:
    """
    Central factory for all 12 payment processors.

    BD Gateways:     bkash, nagad, sslcommerz, amarpay, upay, shurjopay
    International:   stripe, paypal, payoneer, ach
    Crypto:          crypto (BTC, ETH, USDT, USDC, LTC, BCH)
    Bank Transfer:   wire
    """

    _PROCESSOR_MAP = {
        # Bangladesh
        'bkash':        BkashService,
        'nagad':        NagadService,
        'sslcommerz':   SSLCommerzService,
        'amarpay':      AmarPayService,
        'upay':         UpayService,
        'shurjopay':    ShurjoPayService,
        # International
        'stripe':       StripeService,
        'paypal':       PayPalService,
        'payoneer':     PayoneerService,
        'ach':          ACHService,
        # Crypto
        'crypto':       CryptoService,
        'bitcoin':      CryptoService,
        'btc':          CryptoService,
        'eth':          CryptoService,
        'usdt':         CryptoService,
        # Bank
        'wire':         WireTransferService,
        'bank':         WireTransferService,
        'bank_transfer': WireTransferService,
    }

    _GATEWAY_META = [
        # Bangladesh
        {'name':'bkash',      'display_name':'bKash',       'region':'BD',     'currencies':['BDT'], 'color':'#E2136E', 'instant':True,  'sort_order':1},
        {'name':'nagad',      'display_name':'Nagad',        'region':'BD',     'currencies':['BDT'], 'color':'#F7941D', 'instant':True,  'sort_order':2},
        {'name':'sslcommerz', 'display_name':'SSLCommerz',   'region':'BD',     'currencies':['BDT'], 'color':'#0072BC', 'instant':False, 'sort_order':3},
        {'name':'amarpay',    'display_name':'AmarPay',      'region':'BD',     'currencies':['BDT'], 'color':'#00AEEF', 'instant':False, 'sort_order':4},
        {'name':'upay',       'display_name':'Upay',          'region':'BD',     'currencies':['BDT'], 'color':'#005BAA', 'instant':False, 'sort_order':5},
        {'name':'shurjopay',  'display_name':'ShurjoPay',    'region':'BD',     'currencies':['BDT'], 'color':'#6A0DAD', 'instant':False, 'sort_order':6},
        # International
        {'name':'stripe',     'display_name':'Stripe',        'region':'GLOBAL', 'currencies':['USD','EUR','GBP','AUD','CAD'], 'color':'#635BFF', 'instant':False, 'sort_order':7},
        {'name':'paypal',     'display_name':'PayPal',         'region':'GLOBAL', 'currencies':['USD','EUR','GBP'],              'color':'#003087', 'instant':False, 'sort_order':8},
        {'name':'payoneer',   'display_name':'Payoneer',       'region':'GLOBAL', 'currencies':['USD','EUR','GBP'],              'color':'#FF4800', 'instant':False, 'sort_order':9},
        {'name':'ach',        'display_name':'ACH (US Bank)',  'region':'US',     'currencies':['USD'],                          'color':'#0A6640', 'instant':False, 'sort_order':10},
        # Crypto
        {'name':'crypto',     'display_name':'Cryptocurrency', 'region':'GLOBAL', 'currencies':['BTC','ETH','USDT','USDC','LTC','BCH'], 'color':'#F7931A', 'instant':False, 'sort_order':11},
        # Bank Transfer
        {'name':'wire',       'display_name':'Wire Transfer',  'region':'GLOBAL', 'currencies':['BDT','USD','EUR','GBP'],        'color':'#2C3E50', 'instant':False, 'sort_order':12},
    ]

    @staticmethod
    def get_processor(gateway_name: str):
        key = gateway_name.lower().replace('-', '').replace('_', '').strip()

        # Aliases
        aliases = {
            'ssl':           'sslcommerz',
            'aamarpay':      'amarpay',
            'ucbupay':       'upay',
            'shurjo':        'shurjopay',
            'btc':           'crypto',
            'bitcoin':       'crypto',
            'eth':           'crypto',
            'ethereum':      'crypto',
            'usdt':          'crypto',
            'usdc':          'crypto',
            'bank':          'wire',
            'banktransfer':  'wire',
            'wiretransfer':  'wire',
        }
        key = aliases.get(key, key)

        processor_class = PaymentFactory._PROCESSOR_MAP.get(key)
        if not processor_class:
            supported = ', '.join(set(PaymentFactory._PROCESSOR_MAP.keys()))
            raise ValueError(f"Unsupported gateway: '{gateway_name}'. Supported: {supported}")

        return processor_class()

    @staticmethod
    def get_available_gateways():
        return PaymentFactory._GATEWAY_META

    @staticmethod
    def get_gateway_info(gateway_name: str) -> dict:
        key = gateway_name.lower()
        for gw in PaymentFactory._GATEWAY_META:
            if gw['name'] == key:
                return gw
        return {}

    @staticmethod
    def get_bd_gateways() -> list:
        return [g for g in PaymentFactory._GATEWAY_META if g.get('region') == 'BD']

    @staticmethod
    def get_global_gateways() -> list:
        return [g for g in PaymentFactory._GATEWAY_META if g.get('region') in ('GLOBAL','US')]

    @staticmethod
    def get_crypto_gateways() -> list:
        return [g for g in PaymentFactory._GATEWAY_META if g.get('name') == 'crypto']

    @staticmethod
    def get_deposit_gateways() -> list:
        return PaymentFactory._GATEWAY_META  # all support deposit

    @staticmethod
    def get_withdrawal_gateways() -> list:
        return PaymentFactory._GATEWAY_META  # all support withdrawal

    @staticmethod
    def is_gateway_supported(gateway_name: str, operation: str = 'deposit') -> bool:
        info = PaymentFactory.get_gateway_info(gateway_name)
        return bool(info)

    @staticmethod
    def get_all_gateway_names() -> list:
        return [g['name'] for g in PaymentFactory._GATEWAY_META]
