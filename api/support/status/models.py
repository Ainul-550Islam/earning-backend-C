"""api/support/status/models.py"""
from django.db import models
from django.conf import settings

class StatusIncident(models.Model):
    TYPE_CHOICES = [("outage","Outage"),("degraded","Degraded"),("maintenance","Maintenance"),("incident","Incident")]
    title=models.CharField(max_length=300); type=models.CharField(max_length=20,choices=TYPE_CHOICES)
    description=models.TextField(blank=True,default=""); affected_services=models.JSONField(default=list)
    status=models.CharField(max_length=20,default="active",db_index=True); resolution_note=models.TextField(blank=True,default="")
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True); resolved_at=models.DateTimeField(null=True,blank=True)
    class Meta: app_label="support"; db_table="support_status_incident"; ordering=["-created_at"]
    def __str__(self): return f"[{self.type.upper()}] {self.title}"