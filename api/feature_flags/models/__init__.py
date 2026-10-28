"""
Models for Feature Flags & A/B Testing.
"""
from .base import BaseModel
from .feature_flag import FeatureFlag
from .flag_variant import FlagVariant
from .experiment import Experiment
from .experiment_participant import ExperimentParticipant
from .rollout_rule import RolloutRule
from .flag_analytics import FlagAnalytics

# NEW models (production-readiness additions)
from .permissions import Role, Permission, UserRole
from .audit import AuditLog
from .approval import FlagChangeRequest
from .versioning import FeatureFlagVersion
from .scheduling import ScheduledChange
from .notification import NotificationPreference
from .organization import Organization, OrganizationMember, Team

__all__ = [
    'BaseModel',
    'FeatureFlag',
    'FlagVariant',
    'Experiment',
    'ExperimentParticipant',
    'RolloutRule',
    'FlagAnalytics',
    # NEW
    'Role',
    'Permission',
    'UserRole',
    'AuditLog',
    'FlagChangeRequest',
    'FeatureFlagVersion',
    'ScheduledChange',
    'NotificationPreference',
    'Organization',
    'OrganizationMember',
    'Team',
]
