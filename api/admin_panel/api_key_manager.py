# api/admin_panel/api_key_manager.py
"""API key creation, rotation, and scoping for admin and external access."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache
from api.admin_panel.encryption import generate_api_key, hash_sha256

logger = logging.getLogger(__name__)

class APIKeyManager:
    KEY_SCOPES = {
        'read_only':  ['GET'],
        'admin':      ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        'webhooks':   ['POST'],
        'reporting':  ['GET'],
        'advertiser': ['GET', 'POST'],
        'publisher':  ['GET'],
    }

    @classmethod
    def create_key(cls, name: str, scope: str, actor,
                   expires_days: int = 365, user_id: Any = None) -> Dict:
        raw_key = generate_api_key('apk', 32)
        key_hash = hash_sha256(raw_key)
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            keys_raw = SystemConfig.objects.filter(key='api_keys').first()
            keys = json.loads(keys_raw.value) if keys_raw else []
            import uuid
            key_id = str(uuid.uuid4())
            from datetime import timedelta
            expires_at = (timezone.now() + timedelta(days=expires_days)).isoformat() if expires_days else None
            keys.append({'id': key_id, 'name': name, 'scope': scope,
                         'key_hash': key_hash, 'key_preview': raw_key[:8] + '...',
                         'created_at': timezone.now().isoformat(),
                         'expires_at': expires_at, 'is_active': True, 'user_id': user_id})
            SystemConfig.objects.update_or_create(
                key='api_keys',
                defaults={'value': json.dumps(keys), 'group': 'security', 'value_type': 'json'}
            )
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='create_api_key',
                                  changes={'name': name, 'scope': scope, 'key_id': key_id})
            return {'success': True, 'key_id': key_id, 'api_key': raw_key,
                    'warning': 'Store this key now — it will not be shown again!'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def verify_key(cls, raw_key: str) -> Optional[Dict]:
        key_hash = hash_sha256(raw_key)
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='api_keys')
            keys = json.loads(obj.value)
            for k in keys:
                if k.get('key_hash') == key_hash and k.get('is_active'):
                    if k.get('expires_at'):
                        from django.utils.dateparse import parse_datetime
                        exp = parse_datetime(k['expires_at'])
                        if exp and timezone.now() > exp:
                            return None
                    return k
        except Exception:
            pass
        return None

    @classmethod
    def revoke_key(cls, key_id: str, actor) -> bool:
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='api_keys')
            keys = json.loads(obj.value)
            for k in keys:
                if k.get('id') == key_id:
                    k['is_active'] = False
                    k['revoked_at'] = timezone.now().isoformat()
                    break
            obj.value = json.dumps(keys)
            obj.save()
            return True
        except Exception:
            return False

    @classmethod
    def list_keys(cls) -> List[Dict]:
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='api_keys')
            keys = json.loads(obj.value)
            # Never return key_hash
            return [{k: v for k, v in key.items() if k != 'key_hash'} for key in keys]
        except Exception:
            return []

api_key_manager = APIKeyManager()