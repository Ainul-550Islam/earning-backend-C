# api/payment_gateways/integration_system/integ_exceptions.py

class IntegrationError(Exception):
    def __init__(self, message='Integration error', code='INTEG_ERROR', module=''):
        self.message, self.code, self.module = message, code, module
        super().__init__(message)

class HandlerNotFoundError(IntegrationError):
    def __init__(self, event):
        super().__init__(f'No handler registered for: {event}', 'NO_HANDLER')

class HandlerFailedError(IntegrationError):
    def __init__(self, module, event, original_error):
        self.original_error = original_error
        super().__init__(f'Handler {module} failed for {event}: {original_error}', 'HANDLER_FAILED', module)

class DataValidationError(IntegrationError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(f'Validation error on {field}: {message}', 'VALIDATION_ERROR')

class CircularDependencyError(IntegrationError):
    def __init__(self, chain):
        super().__init__(f'Circular dependency: {" -> ".join(chain)}', 'CIRCULAR_DEP')

class BusPublishError(IntegrationError):
    def __init__(self, event):
        super().__init__(f'Failed to publish event: {event}', 'BUS_PUBLISH_ERROR')

class QueueFullError(IntegrationError):
    def __init__(self, queue, size):
        super().__init__(f'Queue {queue} is full ({size} messages)', 'QUEUE_FULL')

class AuthBridgeError(IntegrationError):
    def __init__(self, user, permission):
        super().__init__(f'User lacks permission: {permission}', 'AUTH_DENIED')

class FallbackExhaustedError(IntegrationError):
    def __init__(self, strategy, attempts):
        super().__init__(f'All fallbacks exhausted after {attempts} attempts: {strategy}', 'FALLBACK_EXHAUSTED')

class SyncConflictError(IntegrationError):
    def __init__(self, field, our_value, their_value):
        self.our_value, self.their_value = our_value, their_value
        super().__init__(f'Sync conflict on {field}: ours={our_value} theirs={their_value}', 'SYNC_CONFLICT')
