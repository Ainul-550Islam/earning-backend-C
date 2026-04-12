"""API endpoint registry models."""
from django.db import models
from ..models import AdvertiserPortalBaseModel


class APIEndpoint(AdvertiserPortalBaseModel):
    path = models.CharField(max_length=500, db_index=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True, db_index=True)
    allowed_methods = models.JSONField(default=list)
    class Meta:
        ordering = ['path']
    def __str__(self):
        return f"APIEndpoint {self.path}"


class RESTEndpoint(AdvertiserPortalBaseModel):
    endpoint = models.OneToOneField(APIEndpoint, on_delete=models.CASCADE, related_name='rest')
    http_method = models.CharField(max_length=10)
    request_schema = models.JSONField(default=dict)
    response_schema = models.JSONField(default=dict)
    def __str__(self):
        return f"REST {self.http_method} {self.endpoint_id}"


class GraphQLEndpoint(AdvertiserPortalBaseModel):
    endpoint = models.ForeignKey(APIEndpoint, on_delete=models.CASCADE, related_name='graphql_ops')
    operation_type = models.CharField(max_length=20)
    operation_name = models.CharField(max_length=200)
    def __str__(self):
        return f"GraphQL {self.operation_name}"


class WebSocketEndpoint(AdvertiserPortalBaseModel):
    endpoint = models.OneToOneField(APIEndpoint, on_delete=models.CASCADE, related_name='websocket')
    channel_name = models.CharField(max_length=200)
    def __str__(self):
        return f"WebSocket {self.channel_name}"


class APIDocumentation(AdvertiserPortalBaseModel):
    endpoint = models.ForeignKey(APIEndpoint, on_delete=models.CASCADE, related_name='docs')
    summary = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=10, default='v1')
    def __str__(self):
        return f"APIDoc {self.endpoint_id}"


class APIVersion(AdvertiserPortalBaseModel):
    version = models.CharField(max_length=10, unique=True)
    status = models.CharField(max_length=20, default='current', db_index=True)
    release_date = models.DateField()
    class Meta:
        ordering = ['-release_date']
    def __str__(self):
        return f"API {self.version} [{self.status}]"


class APIAuthentication(AdvertiserPortalBaseModel):
    endpoint = models.ForeignKey(APIEndpoint, on_delete=models.CASCADE, related_name='auth_schemes')
    auth_type = models.CharField(max_length=30)
    scopes_required = models.JSONField(default=list)
    def __str__(self):
        return f"Auth [{self.auth_type}]"


class APIRateLimit(AdvertiserPortalBaseModel):
    endpoint = models.ForeignKey(APIEndpoint, on_delete=models.CASCADE, related_name='rate_limits')
    requests_per_minute = models.IntegerField(default=60)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"RateLimit {self.endpoint_id} {self.requests_per_minute}/min"
