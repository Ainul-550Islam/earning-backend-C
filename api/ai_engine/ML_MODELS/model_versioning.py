"""
api/ai_engine/ML_MODELS/model_versioning.py
============================================
Model Versioning — semantic version management for ML models।
Version bump, comparison, lifecycle management।
"""
import re
import logging
logger = logging.getLogger(__name__)


class ModelVersionManager:
    """Semantic version management for AI models।"""

    @staticmethod
    def parse(version: str) -> tuple:
        """'1.2.3' → (1, 2, 3)"""
        match = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?$', version)
        if not match:
            raise ValueError(f"Invalid version: {version}")
        return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))

    @staticmethod
    def bump(version: str, bump_type: str = 'patch') -> str:
        """Bump version: major/minor/patch।"""
        major, minor, patch = ModelVersionManager.parse(version)
        if bump_type == 'major':    return f"{major + 1}.0.0"
        elif bump_type == 'minor':  return f"{major}.{minor + 1}.0"
        else:                       return f"{major}.{minor}.{patch + 1}"

    @staticmethod
    def is_newer(v1: str, v2: str) -> bool:
        """v1 > v2?"""
        return ModelVersionManager.parse(v1) > ModelVersionManager.parse(v2)

    @staticmethod
    def compare(v1: str, v2: str) -> int:
        """Return 1 if v1 > v2, -1 if v1 < v2, 0 if equal।"""
        p1 = ModelVersionManager.parse(v1)
        p2 = ModelVersionManager.parse(v2)
        if p1 > p2:   return 1
        elif p1 < p2: return -1
        return 0

    @staticmethod
    def get_next_version(ai_model_id: str) -> str:
        """Model এর next version string generate করো।"""
        from api.ai_engine.models import ModelVersion
        latest = ModelVersion.objects.filter(
            ai_model_id=ai_model_id
        ).order_by('-trained_at').first()
        if not latest:
            return '1.0.0'
        try:
            return ModelVersionManager.bump(latest.version, 'minor')
        except Exception:
            return '1.0.0'

    @staticmethod
    def list_versions(ai_model_id: str) -> list:
        """Model এর সব versions list করো।"""
        from api.ai_engine.models import ModelVersion
        versions = ModelVersion.objects.filter(
            ai_model_id=ai_model_id
        ).order_by('-trained_at').values('version', 'is_active', 'trained_at', 'accuracy')
        return list(versions)

    @staticmethod
    def rollback_to_version(ai_model_id: str, target_version: str) -> dict:
        """Specific version এ rollback করো।"""
        from api.ai_engine.models import ModelVersion
        try:
            ModelVersion.objects.filter(ai_model_id=ai_model_id).update(is_active=False)
            target = ModelVersion.objects.get(
                ai_model_id=ai_model_id, version=target_version
            )
            target.is_active = True
            target.save(update_fields=['is_active'])
            logger.info(f"Rolled back model {ai_model_id} to version {target_version}")
            return {'success': True, 'version': target_version}
        except ModelVersion.DoesNotExist:
            return {'success': False, 'error': f'Version {target_version} not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
