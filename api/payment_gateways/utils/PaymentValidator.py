# api/payment_gateways/utils/PaymentValidator.py

import re
import phonenumbers
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from ..models import PaymentGateway, GatewayTransaction, PayoutRequest


class PaymentValidator:
    """Comprehensive Payment Validation Utility"""
    
    # Regex patterns for validation
    BKASH_PATTERN = r'^01[3-9]\d{8}$'
    NAGAD_PATTERN = r'^01[3-9]\d{8}$'
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    BANK_ACCOUNT_PATTERN = r'^\d{9,18}$'
    SWIFT_CODE_PATTERN = r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$'
    IBAN_PATTERN = r'^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$'
    
    @staticmethod
    def validate_amount(amount, gateway_name=None, user=None, transaction_type='deposit'):
        """
        Validate payment amount
        
        Args:
            amount (Decimal/float/int): Amount to validate
            gateway_name (str): Gateway name for gateway-specific limits
            user (User): User object for user-specific limits
            transaction_type (str): 'deposit' or 'withdrawal'
            
        Returns:
            Decimal: Validated amount
            
        Raises:
            ValidationError: If validation fails
        """
        # Convert to Decimal
        try:
            amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except:
            raise ValidationError('Invalid amount format')
        
        # Basic validations
        if amount <= 0:
            raise ValidationError('Amount must be greater than 0')
        
        # Gateway-specific validations
        if gateway_name:
            try:
                gateway = PaymentGateway.objects.get(name=gateway_name)
                
                if amount < gateway.minimum_amount:
                    raise ValidationError(
                        f'Minimum amount for {gateway.display_name} is {gateway.minimum_amount}'
                    )
                
                if amount > gateway.maximum_amount:
                    raise ValidationError(
                        f'Maximum amount for {gateway.display_name} is {gateway.maximum_amount}'
                    )
                
                # Check if gateway supports the operation
                if transaction_type == 'deposit' and not gateway.supports_deposit:
                    raise ValidationError(f'{gateway.display_name} does not support deposits')
                
                if transaction_type == 'withdrawal' and not gateway.supports_withdrawal:
                    raise ValidationError(f'{gateway.display_name} does not support withdrawals')
                    
            except PaymentGateway.DoesNotExist:
                pass
        
        # User-specific validations for withdrawals
        if user and transaction_type == 'withdrawal':
            # Check user balance
            if user.balance < amount:
                raise ValidationError('Insufficient balance')
            
            # Check daily withdrawal limit
            today = timezone.now().date()
            daily_withdrawals = PayoutRequest.objects.filter(
                user=user,
                created_at__date=today,
                status__in=['pending', 'approved', 'processing', 'completed']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            daily_limit = Decimal('50000')  # 50,000 BDT daily limit
            
            if daily_withdrawals + amount > daily_limit:
                raise ValidationError(f'Daily withdrawal limit exceeded. Remaining: {daily_limit - daily_withdrawals}')
            
            # Check minimum withdrawal amount
            if amount < Decimal('100'):
                raise ValidationError('Minimum withdrawal amount is 100')
        
        return amount
    
    @staticmethod
    def validate_phone_number(phone_number, country_code='BD'):
        """
        Validate phone number using phonenumbers library
        
        Args:
            phone_number (str): Phone number to validate
            country_code (str): Country code (default: 'BD' for Bangladesh)
            
        Returns:
            str: Formatted phone number
            
        Raises:
            ValidationError: If phone number is invalid
        """
        try:
            parsed_number = phonenumbers.parse(phone_number, country_code)
            
            if not phonenumbers.is_valid_number(parsed_number):
                raise ValidationError('Invalid phone number')
            
            # Format as E.164
            formatted_number = phonenumbers.format_number(
                parsed_number, 
                phonenumbers.PhoneNumberFormat.E164
            )
            
            return formatted_number
            
        except phonenumbers.NumberParseException:
            raise ValidationError('Invalid phone number format')
    
    @staticmethod
    def validate_bkash_number(account_number):
        """
        Validate bKash account number
        
        Args:
            account_number (str): bKash account number
            
        Returns:
            str: Validated account number
            
        Raises:
            ValidationError: If account number is invalid
        """
        if not re.match(PaymentValidator.BKASH_PATTERN, account_number):
            raise ValidationError(
                'Invalid bKash account number. Must be 11 digits starting with 013-019'
            )
        
        # Check digit validation (simple Luhn-like check)
        digits = [int(d) for d in account_number]
        if sum(digits) % 10 == 0:
            raise ValidationError('Invalid bKash account number')
        
        return account_number
    
    @staticmethod
    def validate_nagad_number(account_number):
        """
        Validate Nagad account number
        
        Args:
            account_number (str): Nagad account number
            
        Returns:
            str: Validated account number
            
        Raises:
            ValidationError: If account number is invalid
        """
        if not re.match(PaymentValidator.NAGAD_PATTERN, account_number):
            raise ValidationError(
                'Invalid Nagad account number. Must be 11 digits starting with 013-019'
            )
        
        return account_number
    
    @staticmethod
    def validate_email(email):
        """
        Validate email address
        
        Args:
            email (str): Email address
            
        Returns:
            str: Validated email
            
        Raises:
            ValidationError: If email is invalid
        """
        if not re.match(PaymentValidator.EMAIL_PATTERN, email):
            raise ValidationError('Invalid email address')
        
        # Check for disposable emails
        disposable_domains = [
            'tempmail.com', 'throwaway.com', 'guerrillamail.com',
            'mailinator.com', '10minutemail.com', 'yopmail.com'
        ]
        
        domain = email.split('@')[1].lower()
        if domain in disposable_domains:
            raise ValidationError('Disposable email addresses are not allowed')
        
        return email.lower()
    
    @staticmethod
    def validate_bank_account(account_number, bank_name=None):
        """
        Validate bank account number
        
        Args:
            account_number (str): Bank account number
            bank_name (str): Bank name for specific validations
            
        Returns:
            str: Validated account number
            
        Raises:
            ValidationError: If account number is invalid
        """
        # Remove spaces and dashes
        account_number = re.sub(r'[\s-]', '', account_number)
        
        if not re.match(PaymentValidator.BANK_ACCOUNT_PATTERN, account_number):
            raise ValidationError('Invalid bank account number')
        
        # Bank-specific validations
        if bank_name:
            bank_name_lower = bank_name.lower()
            
            # DBBL account numbers are 16 digits
            if 'dutch' in bank_name_lower or 'dbl' in bank_name_lower:
                if len(account_number) != 16:
                    raise ValidationError('DBBL account numbers must be 16 digits')
            
            # Standard Chartered account numbers are 12 digits
            elif 'standard' in bank_name_lower or 'chartered' in bank_name_lower:
                if len(account_number) != 12:
                    raise ValidationError('Standard Chartered account numbers must be 12 digits')
        
        return account_number
    
    @staticmethod
    def validate_swift_code(swift_code):
        """
        Validate SWIFT/BIC code
        
        Args:
            swift_code (str): SWIFT/BIC code
            
        Returns:
            str: Validated SWIFT code
            
        Raises:
            ValidationError: If SWIFT code is invalid
        """
        swift_code = swift_code.upper().replace(' ', '')
        
        if not re.match(PaymentValidator.SWIFT_CODE_PATTERN, swift_code):
            raise ValidationError('Invalid SWIFT/BIC code')
        
        return swift_code
    
    @staticmethod
    def validate_iban(iban):
        """
        Validate IBAN
        
        Args:
            iban (str): IBAN
            
        Returns:
            str: Validated IBAN
            
        Raises:
            ValidationError: If IBAN is invalid
        """
        iban = iban.upper().replace(' ', '')
        
        if not re.match(PaymentValidator.IBAN_PATTERN, iban):
            raise ValidationError('Invalid IBAN')
        
        # Basic IBAN validation (mod 97 check)
        if len(iban) < 15 or len(iban) > 34:
            raise ValidationError('Invalid IBAN length')
        
        return iban
    
    @staticmethod
    def validate_transaction_reference(reference_id):
        """
        Validate transaction reference ID
        
        Args:
            reference_id (str): Transaction reference ID
            
        Returns:
            str: Validated reference ID
            
        Raises:
            ValidationError: If reference ID is invalid
        """
        if not reference_id or len(reference_id) < 5:
            raise ValidationError('Invalid transaction reference ID')
        
        # Check if reference already exists
        if GatewayTransaction.objects.filter(reference_id=reference_id).exists():
            raise ValidationError('GatewayTransaction reference ID already exists')
        
        return reference_id
    
    @staticmethod
    def validate_payment_method(user, gateway, account_number, account_name):
        """
        Validate payment method
        
        Args:
            user (User): User object
            gateway (str): Gateway name
            account_number (str): Account number
            account_name (str): Account holder name
            
        Returns:
            dict: Validated payment method data
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        if not gateway:
            raise ValidationError('Payment gateway is required')
        
        if not account_number:
            raise ValidationError('Account number is required')
        
        if not account_name or len(account_name.strip()) < 3:
            raise ValidationError('Account holder name is required')
        
        # Gateway-specific validations
        gateway_lower = gateway.lower()
        
        if gateway_lower in ['bkash', 'nagad']:
            if gateway_lower == 'bkash':
                account_number = PaymentValidator.validate_bkash_number(account_number)
            elif gateway_lower == 'nagad':
                account_number = PaymentValidator.validate_nagad_number(account_number)
            
            # Validate account name (should match registered name)
            if len(account_name) < 4:
                raise ValidationError('Invalid account holder name')
        
        elif gateway_lower == 'paypal':
            account_number = PaymentValidator.validate_email(account_number)
        
        elif gateway_lower in ['bank', 'bank_transfer']:
            account_number = PaymentValidator.validate_bank_account(account_number)
        
        # Check for duplicate payment method
        from ..models import PaymentMethod
        if PaymentMethod.objects.filter(
            user=user,
            gateway=gateway,
            account_number=account_number
        ).exists():
            raise ValidationError('This payment method is already added')
        
        return {
            'gateway': gateway,
            'account_number': account_number,
            'account_name': account_name.strip()
        }
    
    @staticmethod
    def validate_user_kyc(user):
        """
        Validate user KYC status
        
        Args:
            user (User): User object
            
        Returns:
            bool: True if KYC is complete
            
        Raises:
            ValidationError: If KYC is not complete
        """
        # Check if user is verified
        if not user.is_verified:
            raise ValidationError('User account is not verified')
        
        # Check if user has completed KYC
        # Assuming KYC info is stored in UserProfile or similar model
        try:
            profile = user.userprofile
            
            # Basic KYC checks
            required_fields = ['nid_number', 'date_of_birth', 'address']
            for field in required_fields:
                if not getattr(profile, field, None):
                    raise ValidationError(f'KYC incomplete: {field} is required')
            
            # Check if KYC is approved
            if not getattr(profile, 'kyc_verified', False):
                raise ValidationError('KYC verification is pending')
                
        except AttributeError:
            raise ValidationError('User profile not found')
        
        return True
    
    @staticmethod
    def validate_withdrawal_request(user, amount, payment_method):
        """
        Validate withdrawal request
        
        Args:
            user (User): User object
            amount (Decimal): Withdrawal amount
            payment_method (PaymentMethod): Payment method
            
        Returns:
            dict: Validated withdrawal data
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate amount
        amount = PaymentValidator.validate_amount(
            amount, 
            payment_method.gateway, 
            user, 
            'withdrawal'
        )
        
        # Validate payment method
        if not payment_method.is_verified:
            raise ValidationError('Payment method is not verified')
        
        # Validate user KYC
        PaymentValidator.validate_user_kyc(user)
        
        # Check recent withdrawal attempts
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        recent_withdrawals = PayoutRequest.objects.filter(
            user=user,
            created_at__gte=one_hour_ago,
            status__in=['pending', 'processing']
        ).count()
        
        if recent_withdrawals >= 3:
            raise ValidationError('Too many withdrawal attempts. Please try again later.')
        
        return {
            'amount': amount,
            'payment_method': payment_method,
            'user': user
        }
    
    @staticmethod
    def calculate_transaction_fee(amount, gateway_name=None):
        """
        Calculate transaction fee
        
        Args:
            amount (Decimal): GatewayTransaction amount
            gateway_name (str): Gateway name
            
        Returns:
            dict: {'fee': Decimal, 'net_amount': Decimal}
        """
        amount = Decimal(str(amount))
        
        # Default fee structure
        default_fee_percentage = Decimal('1.5')  # 1.5%
        default_min_fee = Decimal('5')  # 5 BDT/USD
        default_max_fee = Decimal('500')  # 500 BDT/USD
        
        # Gateway-specific fees
        gateway_fees = {
            'bkash': {'percentage': Decimal('1.85'), 'min': Decimal('5'), 'max': Decimal('50')},
            'nagad': {'percentage': Decimal('1.49'), 'min': Decimal('5'), 'max': Decimal('50')},
            'stripe': {'percentage': Decimal('2.9'), 'fixed': Decimal('0.30'), 'min': Decimal('0.30')},
            'paypal': {'percentage': Decimal('2.4'), 'fixed': Decimal('0.30'), 'min': Decimal('0.30')},
        }
        
        if gateway_name and gateway_name.lower() in gateway_fees:
            fee_config = gateway_fees[gateway_name.lower()]
            
            # Calculate percentage fee
            percentage_fee = (amount * fee_config['percentage']) / Decimal('100')
            
            # Add fixed fee if exists
            if 'fixed' in fee_config:
                percentage_fee += fee_config['fixed']
            
            # Apply minimum fee
            min_fee = fee_config.get('min', default_min_fee)
            if percentage_fee < min_fee:
                fee = min_fee
            else:
                fee = percentage_fee
            
            # Apply maximum fee
            max_fee = fee_config.get('max', default_max_fee)
            if fee > max_fee:
                fee = max_fee
                
        else:
            # Use default fee calculation
            percentage_fee = (amount * default_fee_percentage) / Decimal('100')
            
            if percentage_fee < default_min_fee:
                fee = default_min_fee
            elif percentage_fee > default_max_fee:
                fee = default_max_fee
            else:
                fee = percentage_fee
        
        # Ensure fee doesn't exceed amount
        if fee >= amount:
            fee = amount * Decimal('0.5')  # Cap at 50% of amount
        
        fee = fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        net_amount = (amount - fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return {
            'fee': fee,
            'net_amount': net_amount,
            'fee_percentage': fee / amount * Decimal('100') if amount > 0 else Decimal('0')
        }