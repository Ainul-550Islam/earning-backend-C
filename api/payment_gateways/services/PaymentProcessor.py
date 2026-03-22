# api/payment_gateways/services/PaymentProcessor.py

from abc import ABC, abstractmethod
from api.payment_gateways.models import GatewayTransaction as db_GatewayTransaction, PaymentGateway
from django.utils import timezone
from decimal import Decimal


class PaymentProcessor(ABC):
    """Abstract Base Class for Payment Processors"""
    
    def __init__(self, gateway_name):
        self.gateway_name = gateway_name
        self.gateway_config = self.get_gateway_config()
    
    def get_gateway_config(self):
        """Get gateway configuration from database"""
        try:
            return PaymentGateway.objects.get(name=self.gateway_name)
        except PaymentGateway.DoesNotExist:
            return None
    
    @abstractmethod
    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Process deposit GatewayTransaction"""
        pass
    
    @abstractmethod
    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """Process withdrawal GatewayTransaction"""
        pass
    
    @abstractmethod
    def verify_payment(self, GatewayTransaction_id, **kwargs):
        """Verify payment status"""
        pass
    
    @abstractmethod
    def get_payment_url(self, GatewayTransaction, **kwargs):
        """Generate payment URL for user redirection"""
        pass
    
    def calculate_fee(self, amount):
        """Calculate GatewayTransaction fee"""
        if self.gateway_config:
            fee_percentage = self.gateway_config.GatewayTransaction_fee_percentage
            return (amount * fee_percentage) / 100
        return Decimal('0')
    
    def create_GatewayTransaction(self, user, GatewayTransaction_type, amount, payment_method=None, **kwargs):
        """Create GatewayTransaction record"""
        fee = self.calculate_fee(amount)
        net_amount = amount - fee
        
        GatewayTransaction = GatewayTransaction.objects.create(
            user=user,
            GatewayTransaction_type=GatewayTransaction_type,
            gateway=self.gateway_name,
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            status='pending',
            reference_id=self.generate_reference_id(),
            payment_method=payment_method,
            metadata={
                'gateway': self.gateway_name,
                'processor': self.__class__.__name__,
                **kwargs.get('metadata', {})
            }
        )
        
        return GatewayTransaction
    
    def generate_reference_id(self):
        """Generate unique reference ID"""
        timestamp = int(timezone.now().timestamp() * 1000)
        return f"{self.gateway_name.upper()}_{timestamp}"
    
    def validate_amount(self, amount):
        """Validate amount against gateway limits"""
        if not self.gateway_config:
            return True
        
        amount = Decimal(str(amount))
        
        if amount < self.gateway_config.minimum_amount:
            raise ValueError(
                f"Minimum amount is {self.gateway_config.minimum_amount}"
            )
        
        if amount > self.gateway_config.maximum_amount:
            raise ValueError(
                f"Maximum amount is {self.gateway_config.maximum_amount}"
            )
        
        return True
    
    def update_GatewayTransaction_status(self, GatewayTransaction, status, gateway_reference=None, **kwargs):
        """Update GatewayTransaction status"""
        GatewayTransaction.status = status
        
        if gateway_reference:
            GatewayTransaction.gateway_reference = gateway_reference
        
        if status == 'completed':
            GatewayTransaction.completed_at = timezone.now()
        
        if kwargs.get('metadata'):
            GatewayTransaction.metadata.update(kwargs['metadata'])
        
        GatewayTransaction.save()
        return GatewayTransaction