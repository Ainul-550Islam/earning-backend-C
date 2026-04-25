# api/payment_gateways/session_manager.py
# Payment session management
import secrets,logging
from django.core.cache import cache
from django.utils import timezone
logger=logging.getLogger(__name__)

class PaymentSessionManager:
    SESSION_TTL=3600
    def create_session(self,user,gateway,amount,currency,metadata=None):
        session_id=secrets.token_urlsafe(32)
        data={'session_id':session_id,'user_id':user.id,'gateway':gateway,'amount':str(amount),'currency':currency,'created_at':timezone.now().isoformat(),'status':'active','metadata':metadata or {}}
        cache.set(f'pg:session:{session_id}',data,self.SESSION_TTL)
        return session_id
    def get_session(self,session_id):
        return cache.get(f'pg:session:{session_id}')
    def update_session(self,session_id,updates):
        data=self.get_session(session_id)
        if not data: return False
        data.update(updates)
        cache.set(f'pg:session:{session_id}',data,self.SESSION_TTL)
        return True
    def complete_session(self,session_id,reference_id):
        return self.update_session(session_id,{'status':'completed','reference_id':reference_id})
    def expire_session(self,session_id):
        cache.delete(f'pg:session:{session_id}')
    def is_valid(self,session_id):
        data=self.get_session(session_id)
        return bool(data and data.get('status')=='active')
    def get_user_active_sessions(self,user):
        try:
            from django_redis import get_redis_connection
            conn=get_redis_connection('default')
            keys=conn.keys(f'pg:session:*')
            sessions=[]
            for key in keys:
                d=cache.get(key.decode().replace(':pg:session:','')); 
                if d and d.get('user_id')==user.id and d.get('status')=='active': sessions.append(d)
            return sessions
        except: return []
session_manager=PaymentSessionManager()
