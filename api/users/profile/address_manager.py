"""
api/users/profile/address_manager.py
User address book — withdrawal + KYC-এর জন্য
"""
import logging
from django.db import models
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User   = get_user_model()


# ─────────────────────────────────────────
# MODEL (users/models.py-তে যোগ করো)
# ─────────────────────────────────────────
# class UserAddress(models.Model):
#     ADDRESS_TYPES = [
#         ('home',     'Home'),
#         ('work',     'Work'),
#         ('billing',  'Billing'),
#         ('shipping', 'Shipping'),
#     ]
#     user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
#     label        = models.CharField(max_length=50, default='Home')
#     address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='home')
#     full_name    = models.CharField(max_length=200)
#     address_line1= models.CharField(max_length=255)
#     address_line2= models.CharField(max_length=255, blank=True)
#     city         = models.CharField(max_length=100)
#     state        = models.CharField(max_length=100, blank=True)
#     postal_code  = models.CharField(max_length=20, blank=True)
#     country      = models.CharField(max_length=100)
#     phone        = models.CharField(max_length=20, blank=True)
#     is_default   = models.BooleanField(default=False)
#     created_at   = models.DateTimeField(auto_now_add=True)
#
#     class Meta:
#         db_table = 'users_address'
#         ordering = ['-is_default', '-created_at']


class AddressManager:

    def get_all(self, user) -> list:
        try:
            from django.apps import apps
            Address = apps.get_model('users', 'UserAddress')
            return list(Address.objects.filter(user=user).values())
        except Exception:
            return []

    def get_default(self, user) -> dict | None:
        try:
            from django.apps import apps
            Address = apps.get_model('users', 'UserAddress')
            addr    = Address.objects.filter(user=user, is_default=True).first()
            return addr.__dict__ if addr else None
        except Exception:
            return None

    def add(self, user, data: dict) -> dict:
        try:
            from django.apps import apps
            Address = apps.get_model('users', 'UserAddress')

            # First address = default
            is_first = not Address.objects.filter(user=user).exists()

            addr = Address.objects.create(
                user          = user,
                label         = data.get('label', 'Home'),
                address_type  = data.get('address_type', 'home'),
                full_name     = data.get('full_name', ''),
                address_line1 = data.get('address_line1', ''),
                address_line2 = data.get('address_line2', ''),
                city          = data.get('city', ''),
                state         = data.get('state', ''),
                postal_code   = data.get('postal_code', ''),
                country       = data.get('country', ''),
                phone         = data.get('phone', ''),
                is_default    = data.get('is_default', is_first),
            )
            if addr.is_default:
                self._clear_other_defaults(user, addr.id)
            return {'id': str(addr.id), 'label': addr.label}
        except Exception as e:
            logger.error(f'Address add failed: {e}')
            return {}

    def set_default(self, user, address_id: str) -> bool:
        try:
            from django.apps import apps
            Address = apps.get_model('users', 'UserAddress')
            # Clear all defaults
            Address.objects.filter(user=user).update(is_default=False)
            # Set new default
            Address.objects.filter(user=user, id=address_id).update(is_default=True)
            return True
        except Exception:
            return False

    def delete(self, user, address_id: str) -> bool:
        try:
            from django.apps import apps
            Address = apps.get_model('users', 'UserAddress')
            deleted, _ = Address.objects.filter(user=user, id=address_id).delete()
            return deleted > 0
        except Exception:
            return False

    def _clear_other_defaults(self, user, exclude_id) -> None:
        try:
            from django.apps import apps
            Address = apps.get_model('users', 'UserAddress')
            Address.objects.filter(user=user, is_default=True).exclude(id=exclude_id).update(is_default=False)
        except Exception:
            pass


# Singleton
address_manager = AddressManager()
