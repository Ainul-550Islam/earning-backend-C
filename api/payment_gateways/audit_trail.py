# api/payment_gateways/audit_trail.py
# Immutable audit trail for all payment operations
import logging
from django.utils import timezone
logger=logging.getLogger(__name__)

class AuditTrail:
    def log(self,event_type,user=None,resource=None,old_value=None,new_value=None,request=None,notes=''):
        from api.payment_gateways.integration_system.integ_audit_logs import audit_logger
        ip=''
        if request:
            from api.payment_gateways.helpers import get_client_ip
            ip=get_client_ip(request)
        audit_logger.log(event_type=event_type,source_module='api.payment_gateways',user_id=getattr(user,'id',None),payload={'resource':str(resource),'old':str(old_value),'new':str(new_value),'notes':notes},result={'action':'logged'},ip_address=ip,success=True)
    def log_deposit(self,user,deposit,request=None):
        self.log('deposit.created',user=user,resource=deposit.reference_id,new_value=f'{deposit.amount} {deposit.currency}',request=request)
    def log_withdrawal(self,user,payout,request=None):
        self.log('withdrawal.requested',user=user,resource=payout.reference_id,new_value=f'{payout.amount} {payout.currency}',request=request)
    def log_admin_action(self,admin,action,target,notes=''):
        self.log(f'admin.{action}',user=admin,resource=str(target),notes=notes)
    def log_credential_access(self,admin,gateway):
        self.log('credential.accessed',user=admin,resource=gateway,notes='Gateway credentials accessed')
    def get_trail(self,user_id=None,event_type=None,hours=24,limit=100):
        from api.payment_gateways.integration_system.integ_audit_logs import AuditLogger
        return AuditLogger().get_recent(event_type=event_type,user_id=user_id,hours=hours,limit=limit)
audit_trail=AuditTrail()
