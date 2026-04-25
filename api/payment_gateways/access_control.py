# api/payment_gateways/access_control.py
# Role-based access control
import logging
logger=logging.getLogger(__name__)

ROLES={'admin':{'all'},'advertiser':{'view_own_offers','manage_offers','view_conversions','view_analytics','manage_campaigns'},'publisher':{'view_offers','view_own_conversions','view_own_analytics','request_payout','create_smartlink','create_locker'},'staff':{'view_all_transactions','approve_payouts','view_analytics','manage_users'}}

class AccessControl:
    def has_permission(self,user,permission):
        if user.is_superuser: return True
        user_role=self.get_role(user)
        role_perms=ROLES.get(user_role,set())
        return 'all' in role_perms or permission in role_perms
    def get_role(self,user):
        if user.is_superuser or user.is_staff: return 'admin' if user.is_superuser else 'staff'
        try:
            from api.payment_gateways.publisher.models import AdvertiserProfile
            AdvertiserProfile.objects.get(user=user,status='active')
            return 'advertiser'
        except: pass
        return 'publisher'
    def require_permission(self,user,permission):
        if not self.has_permission(user,permission):
            from api.payment_gateways.exceptions import InsufficientPermissionsException
            raise InsufficientPermissionsException(f'Permission denied: {permission}')
    def get_user_permissions(self,user):
        role=self.get_role(user)
        perms=ROLES.get(role,set())
        return {'role':role,'permissions':list(perms),'is_admin':'all' in perms}
access_control=AccessControl()
