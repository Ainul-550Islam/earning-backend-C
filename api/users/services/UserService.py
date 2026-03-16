from django.contrib.auth import authenticate
from django.db import transaction
from ..models import User, LoginHistory
from ..utils import get_client_ip, generate_referral_code


class UserService:
    
    @staticmethod
    @transaction.atomic
    def create_user(validated_data):
        """Create new user with profile"""
        referred_by = validated_data.pop('referred_by', None)
        password = validated_data.pop('password')
        
        user = User(**validated_data)
        user.set_password(password)
        
        if referred_by:
            user.referred_by = referred_by
        
        user.referral_code = generate_referral_code(user.username)
        user.save()
        
        return user
    
    @staticmethod
    def authenticate_user(username_or_email, password):
        """Authenticate user by username or email"""
        user = User.objects.filter(username=username_or_email).first() or \
               User.objects.filter(email=username_or_email).first()
        
        if user and user.check_password(password):
            return user
        return None
    
    @staticmethod
    def log_login(user, request):
        """Log user login history"""
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        LoginHistory.objects.create(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            is_successful=True
        )
        
        user.last_login_ip = ip_address
        user.save()