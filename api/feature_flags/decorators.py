"""
Decorators for Feature Flags & A/B Testing.

FIX (DRY): the "pull user_id/email/session_id out of args[0].request"
block was previously copy-pasted into all FOUR decorators below. It now
calls `ContextExtractor.from_view_args()` once each — one implementation,
four call sites, instead of four near-identical implementations that
could silently drift apart.
"""
from functools import wraps
from typing import Callable, Any

from .flag_engine import FlagEngine
from .exceptions import FlagNotFoundError, FlagDisabledError
from .utils import ContextExtractor


def feature_flag(
    flag_name: str,
    default_return: Any = None,
    raise_error: bool = False
):
    """
    Decorator to check if a feature flag is enabled.

    Args:
        flag_name: Name of the feature flag
        default_return: Default return value if flag is disabled
        raise_error: Whether to raise an error if flag is disabled

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            engine = FlagEngine()

            try:
                context = ContextExtractor.from_view_args(args)
                is_enabled = engine.is_enabled(flag_name, context)

                if not is_enabled:
                    if raise_error:
                        raise FlagDisabledError(f"Feature flag '{flag_name}' is disabled")
                    return default_return

                return func(*args, **kwargs)
            except FlagNotFoundError:
                if raise_error:
                    raise
                return default_return

        return wrapper
    return decorator


def variant_assignment(experiment_name: str):
    """
    Decorator to assign a user to an experiment variant.

    Args:
        experiment_name: Name of the experiment

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from .experiment_runner import ExperimentRunner
            runner = ExperimentRunner()

            context = ContextExtractor.from_view_args(args)
            variant = runner.assign_variant(experiment_name, context)

            kwargs['variant'] = variant

            return func(*args, **kwargs)

        return wrapper
    return decorator


def track_conversion(experiment_name: str):
    """
    Decorator to track conversion for an experiment.

    Args:
        experiment_name: Name of the experiment

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from .experiment_runner import ExperimentRunner
            runner = ExperimentRunner()

            context = ContextExtractor.from_view_args(args)

            result = func(*args, **kwargs)

            runner.track_conversion(experiment_name, context)

            return result

        return wrapper
    return decorator


def flag_value(flag_name: str, default_value: Any = None):
    """
    Decorator to get the value of a feature flag.

    Args:
        flag_name: Name of the feature flag
        default_value: Default value if flag is disabled

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            engine = FlagEngine()

            context = ContextExtractor.from_view_args(args)
            value = engine.get_value(flag_name, context, default_value)

            kwargs['flag_value'] = value

            return func(*args, **kwargs)

        return wrapper
    return decorator


def require_percentage(percentage: int):
    """
    NEW — Decorator that only executes the wrapped function for a random
    `percentage` slice of calls (independent of any stored flag). Useful
    for ad-hoc canary behavior without creating a full FeatureFlag row.
    Previously documented in the audit as an existing-but-undocumented
    decorator; it did not actually exist in the original code, so it is
    implemented here as a genuinely new, documented utility.

    Args:
        percentage: 0-100, chance the function executes on any given call

    Returns:
        Decorator function
    """
    import random

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if random.randint(0, 99) < percentage:
                return func(*args, **kwargs)
            return None
        return wrapper
    return decorator
