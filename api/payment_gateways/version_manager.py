# api/payment_gateways/version_manager.py
# Version management
import logging
logger=logging.getLogger(__name__)
CURRENT_VERSION='2.0.0'
MINIMUM_SUPPORTED='1.0.0'

class VersionManager:
    def get_version(self): return CURRENT_VERSION
    def check_compatibility(self,client_version):
        try:
            cur=tuple(int(x) for x in CURRENT_VERSION.split('.'))
            cli=tuple(int(x) for x in client_version.split('.'))
            min_v=tuple(int(x) for x in MINIMUM_SUPPORTED.split('.'))
            if cli<min_v: return False,f'Client version {client_version} not supported. Minimum: {MINIMUM_SUPPORTED}'
            return True,''
        except: return True,''
    def get_version_info(self):
        from api.payment_gateways.changelog import get_latest_version,CHANGELOG
        return {'current_version':CURRENT_VERSION,'minimum_supported':MINIMUM_SUPPORTED,'latest_changes':CHANGELOG[0]['changes'][:5] if CHANGELOG else []}
version_manager=VersionManager()
