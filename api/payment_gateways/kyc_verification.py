# api/payment_gateways/kyc_verification.py
# KYC verification integration
import logging
logger = logging.getLogger(__name__)

class KYCVerificationService:
    def get_status(self, user):
        try:
            from api.kyc.models import KYCProfile
            kyc = KYCProfile.objects.get(user=user)
            return {'status':kyc.status,'is_verified':kyc.status=='approved','level':getattr(kyc,'kyc_level',1)}
        except ImportError:
            return {'status':'not_required','is_verified':True,'level':0}
        except: return {'status':'pending','is_verified':False,'level':0}
    def requires_kyc_for_withdrawal(self, user, amount, gateway):
        from api.payment_gateways.compliance import compliance_engine
        check = compliance_engine.requires_kyc(user, amount, gateway)
        if not check['required']: return False, ''
        status = self.get_status(user)
        if status['is_verified']: return False, ''
        return True, f"KYC required: {', '.join(check['documents_needed'])}"
    def initiate_kyc(self, user, level=1):
        try:
            from api.kyc.services import KYCService
            return KYCService().initiate(user, level=level)
        except ImportError: return {'success':False,'error':'KYC app not installed'}
    def verify_identity(self, user, doc_type, doc_number, doc_image=None):
        logger.info(f'KYC identity check: user={user.id} doc={doc_type}')
        try:
            from api.kyc.services import KYCService
            return KYCService().verify(user, doc_type=doc_type, doc_number=doc_number)
        except ImportError: return {'success':True,'status':'approved','note':'KYC bypass — app not installed'}
kyc_service = KYCVerificationService()
