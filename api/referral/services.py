# referral/services.py
from decimal import Decimal
from django.db import transaction
from .models import Referral, ReferralSettings, ReferralEarning
from api.models import User, EarningTask

class ReferralService:
    
    @staticmethod
    def process_signup_bonus(user, referrer):
        """Give signup bonuses to both users"""
        try:
            settings = ReferralSettings.objects.first()
            if not settings or not settings.is_active:
                return
            
            with transaction.atomic():
                # Give bonus to new user
                user.coin_balance += settings.direct_signup_bonus
                user.save()
                
                # Give bonus to referrer
                referrer.coin_balance += settings.referrer_signup_bonus
                referrer.save()
                
                # Create referral relationship
                referral = Referral.objects.create(
                    referrer=referrer,
                    referred_user=user,
                    signup_bonus_given=True
                )
                
                return referral
        except Exception as e:
            print(f"Referral bonus error: {e}")
            return None
    
    @staticmethod
    def process_lifetime_commission(referred_user, coins_earned, source_task):
        """Give commission to referrer when referred user earns"""
        try:
            referral = Referral.objects.get(referred_user=referred_user)
            settings = ReferralSettings.objects.first()
            
            if not settings or not settings.is_active:
                return
            
            # Calculate commission
            commission_amount = coins_earned * (settings.lifetime_commission_rate / 100)
            
            with transaction.atomic():
                # Add commission to referrer
                referrer = referral.referrer
                referrer.coin_balance += commission_amount
                referrer.save()
                
                # Update total commission
                referral.total_commission_earned += commission_amount
                referral.save()
                
                # Log the commission
                ReferralEarning.objects.create(
                    referral=referral,
                    referrer=referrer,
                    referred_user=referred_user,
                    amount=commission_amount,
                    commission_rate=settings.lifetime_commission_rate,
                    source_task=source_task
                )
                
                return commission_amount
        except Referral.DoesNotExist:
            return None
        except Exception as e:
            print(f"Commission error: {e}")
            return None