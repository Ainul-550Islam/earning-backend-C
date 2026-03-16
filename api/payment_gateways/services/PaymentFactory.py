# api/payment_gateways/services/PaymentFactory.py

from .BkashService import BkashService
from .NagadService import NagadService
from .StripeService import StripeService
from .PayPalService import PayPalService


class PaymentFactory:
    """Factory class to create payment processor instances"""
    
    @staticmethod
    def get_processor(gateway_name, **kwargs):
        """
        Get payment processor instance based on gateway name
        
        Args:
            gateway_name (str): Name of the payment gateway
            **kwargs: Additional arguments for processor initialization
            
        Returns:
            PaymentProcessor: Instance of the appropriate payment processor
            
        Raises:
            ValueError: If gateway is not supported
        """
        processors = {
            'bkash': BkashService,
            'nagad': NagadService,
            'stripe': StripeService,
            'paypal': PayPalService,
            'bKash': BkashService,  # Handle different cases
            'Nagad': NagadService,
            'Stripe': StripeService,
            'PayPal': PayPalService,
        }
        
        # Normalize gateway name
        gateway_lower = gateway_name.lower()
        
        # Map normalized name to processor class
        processor_map = {
            'bkash': BkashService,
            'nagad': NagadService,
            'stripe': StripeService,
            'paypal': PayPalService,
        }
        
        processor_class = processor_map.get(gateway_lower)
        
        if not processor_class:
            raise ValueError(f'Unsupported payment gateway: {gateway_name}')
        
        # Create and return processor instance
        return processor_class()
    
    @staticmethod
    def get_available_gateways():
        """Get list of available payment gateways"""
        return [
            {
                'name': 'bkash',
                'display_name': 'bKash',
                'supports_deposit': True,
                'supports_withdrawal': True,
                'currencies': ['BDT'],
                'icon': '[MONEY]'
            },
            {
                'name': 'nagad',
                'display_name': 'Nagad',
                'supports_deposit': True,
                'supports_withdrawal': True,
                'currencies': ['BDT'],
                'icon': '💳'
            },
            {
                'name': 'stripe',
                'display_name': 'Stripe',
                'supports_deposit': True,
                'supports_withdrawal': True,
                'currencies': ['USD', 'EUR', 'GBP'],
                'icon': '💳'
            },
            {
                'name': 'paypal',
                'display_name': 'PayPal',
                'supports_deposit': True,
                'supports_withdrawal': True,
                'currencies': ['USD', 'EUR', 'GBP'],
                'icon': '👛'
            },
        ]
    
    @staticmethod
    def get_gateway_info(gateway_name):
        """Get information about a specific gateway"""
        gateways = PaymentFactory.get_available_gateways()
        
        for gateway in gateways:
            if gateway['name'] == gateway_name.lower():
                return gateway
        
        return None
    
    @staticmethod
    def get_deposit_gateways():
        """Get gateways that support deposits"""
        gateways = PaymentFactory.get_available_gateways()
        return [g for g in gateways if g['supports_deposit']]
    
    @staticmethod
    def get_withdrawal_gateways():
        """Get gateways that support withdrawals"""
        gateways = PaymentFactory.get_available_gateways()
        return [g for g in gateways if g['supports_withdrawal']]
    
    @staticmethod
    def is_gateway_supported(gateway_name, operation='deposit'):
        """
        Check if gateway supports specific operation
        
        Args:
            gateway_name (str): Gateway name
            operation (str): 'deposit' or 'withdrawal'
            
        Returns:
            bool: True if supported, False otherwise
        """
        gateway_info = PaymentFactory.get_gateway_info(gateway_name)
        
        if not gateway_info:
            return False
        
        if operation == 'deposit':
            return gateway_info.get('supports_deposit', False)
        elif operation == 'withdrawal':
            return gateway_info.get('supports_withdrawal', False)
        
        return False