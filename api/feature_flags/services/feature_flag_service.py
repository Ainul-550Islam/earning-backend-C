"""
Feature Flag service for Feature Flags & A/B Testing.

FIX: `create_flag` previously performed ZERO validation — a flag with
rollout_percentage=999 or an empty name could be created by calling this
service directly (bypassing the serializer-level checks). It now raises
`ValueError` via `FlagValidator` before touching the database.

NEW: `clone_flag` and `restore_flag` — genuinely new capabilities (the
prior audit reports described these as "floating code"; in the actual
codebase they did not exist at all, so they're implemented here fresh
and wired to FeatureFlagViewSet.clone_flag / .restore).
"""
from typing import Dict, Any, Optional, List

from ..models.feature_flag import FeatureFlag
from ..flag_engine import FlagEngine
from ..exceptions import FlagNotFoundError
from ..utils import FlagValidator


class FeatureFlagService:
    """
    Service for managing feature flags.
    """

    def __init__(self):
        """Initialize the feature flag service."""
        self.engine = FlagEngine()

    def create_flag(self, data: Dict[str, Any]) -> FeatureFlag:
        """
        Create a new feature flag.

        Raises:
            ValueError: if name or rollout_percentage fail validation, or
                a flag with this name already exists in this environment.
        """
        name = data['name']
        rollout_percentage = data.get('rollout_percentage', 0)
        environment = data.get('environment', 'production')

        # FIX: validation that previously did not exist at the service layer.
        if not FlagValidator.validate_name(name):
            raise ValueError(f"Invalid flag name: '{name}'")
        if not FlagValidator.validate_rollout_percentage(rollout_percentage):
            raise ValueError(f"Invalid rollout_percentage: {rollout_percentage!r}")
        if FeatureFlag.objects.filter(name=name, environment=environment).exists():
            raise ValueError(f"A flag named '{name}' already exists in environment '{environment}'")

        return FeatureFlag.objects.create(
            name=name,
            description=data.get('description', ''),
            flag_type=data.get('flag_type', 'boolean'),
            status=data.get('status', 'draft'),
            default_value=data.get('default_value', {}),
            rollout_percentage=rollout_percentage,
            targeting_rules=data.get('targeting_rules', []),
            metadata=data.get('metadata', {}),
            tags=data.get('tags', []),
            owner=data.get('owner', ''),
            team=data.get('team', ''),
            environment=environment,
            organization=data.get('organization'),
        )

    def get_flag(self, flag_name: str, environment: str = 'production') -> Optional[FeatureFlag]:
        """Get a feature flag by name. `environment` is NEW (multi-env support)."""
        try:
            return FeatureFlag.objects.get(name=flag_name, environment=environment)
        except FeatureFlag.DoesNotExist:
            return None

    def get_flags(self, environment: str = 'production', status: Optional[str] = None) -> List[FeatureFlag]:
        """Get feature flags with optional filters."""
        queryset = FeatureFlag.objects.filter(environment=environment)

        if status:
            queryset = queryset.filter(status=status)

        return list(queryset.order_by('-created_at'))

    def update_flag(self, flag_name: str, data: Dict[str, Any], environment: str = 'production') -> bool:
        """
        Update a feature flag.

        Raises:
            ValueError: if an updated rollout_percentage fails validation.
        """
        flag = self.get_flag(flag_name, environment)

        if not flag:
            return False

        if 'rollout_percentage' in data and not FlagValidator.validate_rollout_percentage(data['rollout_percentage']):
            raise ValueError(f"Invalid rollout_percentage: {data['rollout_percentage']!r}")

        for key, value in data.items():
            if hasattr(flag, key) and key not in ['id', 'created_at', 'updated_at']:
                setattr(flag, key, value)

        flag.save()

        self.engine.clear_flag_cache(flag_name, environment)

        return True

    def delete_flag(self, flag_name: str, environment: str = 'production') -> bool:
        """Delete a feature flag."""
        flag = self.get_flag(flag_name, environment)

        if not flag:
            return False

        self.engine.clear_flag_cache(flag_name, environment)

        flag.delete()

        return True

    def activate_flag(self, flag_name: str, environment: str = 'production') -> bool:
        """Activate a feature flag."""
        return self.update_flag(flag_name, {'status': 'active'}, environment)

    def pause_flag(self, flag_name: str, environment: str = 'production') -> bool:
        """Pause a feature flag."""
        return self.update_flag(flag_name, {'status': 'paused'}, environment)

    def archive_flag(self, flag_name: str, environment: str = 'production') -> bool:
        """Archive a feature flag."""
        return self.update_flag(flag_name, {'status': 'archived'}, environment)

    def restore_flag(self, flag_name: str, environment: str = 'production') -> bool:
        """
        NEW: restore an archived flag back to draft status, ready to be
        re-activated deliberately rather than snapping straight back to
        active.
        """
        return self.update_flag(flag_name, {'status': 'draft'}, environment)

    def clone_flag(self, source_name: str, new_name: str, environment: str = 'production') -> FeatureFlag:
        """
        NEW: clone an existing flag (including its variants) under a new
        name within the same environment. The clone always starts in
        draft status with 0% rollout, regardless of the source flag's
        current state, so cloning can never accidentally turn on a new
        flag in production.

        Raises:
            FlagNotFoundError: if the source flag doesn't exist.
            ValueError: if new_name is invalid or already taken.
        """
        if not FlagValidator.validate_name(new_name):
            raise ValueError(f"Invalid flag name: '{new_name}'")

        source = self.get_flag(source_name, environment)
        if not source:
            raise FlagNotFoundError(f"Source flag '{source_name}' not found in environment '{environment}'")

        if FeatureFlag.objects.filter(name=new_name, environment=environment).exists():
            raise ValueError(f"A flag named '{new_name}' already exists in environment '{environment}'")

        new_flag = FeatureFlag.objects.create(
            name=new_name,
            description=f"Clone of {source_name}",
            flag_type=source.flag_type,
            status=FeatureFlag.Status.DRAFT,
            default_value=source.default_value,
            rollout_percentage=0,
            targeting_rules=source.targeting_rules,
            metadata=source.metadata,
            tags=source.tags,
            owner=source.owner,
            team=source.team,
            environment=source.environment,
            organization=source.organization,
        )

        from ..models.flag_variant import FlagVariant
        for variant in FlagVariant.objects.filter(flag=source):
            FlagVariant.objects.create(
                flag=new_flag,
                name=variant.name,
                description=variant.description,
                value=variant.value,
                weight=variant.weight,
                is_control=variant.is_control,
                is_active=variant.is_active,
                metadata=variant.metadata,
            )

        return new_flag

    def is_enabled(self, flag_name: str, context: Optional[Dict[str, Any]] = None,
                   environment: str = 'production') -> bool:
        """Check if a flag is enabled. `environment` is NEW (multi-env support)."""
        return self.engine.is_enabled(flag_name, context, environment)

    def get_value(self, flag_name: str, context: Optional[Dict[str, Any]] = None, default_value: Any = None,
                  environment: str = 'production') -> Any:
        """Get the value of a flag. `environment` is NEW (multi-env support)."""
        return self.engine.get_value(flag_name, context, default_value, environment)
