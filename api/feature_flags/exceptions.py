"""
Custom exceptions for Feature Flags & A/B Testing.
"""


class FeatureFlagException(Exception):
    """
    Base exception for feature flag errors.
    """
    pass


class FlagNotFoundError(FeatureFlagException):
    """
    Exception raised when a flag is not found.
    """
    pass


class FlagDisabledError(FeatureFlagException):
    """
    Exception raised when a flag is disabled.
    """
    pass


class InvalidFlagTypeError(FeatureFlagException):
    """
    Exception raised when an invalid flag type is provided.
    """
    pass


class InvalidContextError(FeatureFlagException):
    """
    Exception raised when invalid context is provided.
    """
    pass


class ExperimentNotFoundError(FeatureFlagException):
    """
    Exception raised when an experiment is not found.
    """
    pass


class ExperimentNotActiveError(FeatureFlagException):
    """
    Exception raised when an experiment is not active.
    """
    pass


class ExperimentAlreadyRunningError(FeatureFlagException):
    """
    Exception raised when an experiment is already running.
    """
    pass


class InvalidVariantError(FeatureFlagException):
    """
    Exception raised when an invalid variant is provided.
    """
    pass


class RolloutRuleError(FeatureFlagException):
    """
    Exception raised when a rollout rule error occurs.
    """
    pass


class AnalyticsError(FeatureFlagException):
    """
    Exception raised when an analytics error occurs.
    """
    pass


class CacheError(FeatureFlagException):
    """
    Exception raised when a cache error occurs.
    """
    pass
