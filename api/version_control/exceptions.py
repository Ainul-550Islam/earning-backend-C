# =============================================================================
# version_control/exceptions.py
# =============================================================================

from rest_framework import status
from rest_framework.exceptions import APIException


class VersionControlError(APIException):
    status_code  = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "An unexpected version control error occurred."
    default_code   = "version_control_error"


# 400
class InvalidVersionStringError(VersionControlError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "The provided version string does not follow semver format."
    default_code   = "invalid_version_string"


class InvalidPlatformError(VersionControlError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Unrecognised platform identifier."
    default_code   = "invalid_platform"


class InvalidMaintenanceWindowError(VersionControlError):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Maintenance window configuration is invalid."
    default_code   = "invalid_maintenance_window"


# 404
class UpdatePolicyNotFoundError(VersionControlError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "No update policy found for the given platform and version."
    default_code   = "update_policy_not_found"


class MaintenanceNotFoundError(VersionControlError):
    status_code  = status.HTTP_404_NOT_FOUND
    default_detail = "Maintenance schedule not found."
    default_code   = "maintenance_not_found"


# 409
class MaintenanceAlreadyActiveError(VersionControlError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "A maintenance window is already active for this platform."
    default_code   = "maintenance_already_active"


class PolicyAlreadyExistsError(VersionControlError):
    status_code  = status.HTTP_409_CONFLICT
    default_detail = "An active update policy for this platform and version already exists."
    default_code   = "policy_already_exists"


# 503
class MaintenanceModeError(VersionControlError):
    """
    Raised (and returned to clients) when the system is in maintenance mode.
    """
    status_code  = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The service is currently undergoing maintenance. Please try again later."
    default_code   = "maintenance_mode"
