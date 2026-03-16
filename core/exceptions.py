from rest_framework.exceptions import APIException
from rest_framework import status


class CustomAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A server error occurred.'
    default_code = 'error'

    def __init__(self, detail=None, code=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        if detail is not None:
            self.detail = detail
        else:
            self.detail = self.default_detail
        if code is not None:
            self.default_code = code


class ValidationError(CustomAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Validation error.'
    default_code = 'validation_error'


class NotFoundError(CustomAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found.'
    default_code = 'not_found'


class PermissionDeniedError(CustomAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Permission denied.'
    default_code = 'permission_denied'


class UnauthorizedError(CustomAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Unauthorized access.'
    default_code = 'unauthorized'