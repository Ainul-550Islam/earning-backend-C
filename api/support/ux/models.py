"""api/support/ux/models.py"""
from django.db import models
from django.conf import settings

class BrowserPushSubscription(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="push_subscriptions")
    endpoint=models.URLField(max_length=500); subscription_data=models.TextField()
    is_active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: app_label="support"; db_table="support_browser_push_sub"; unique_together=[["user","endpoint"]]

class UserFeedback(models.Model):
    TYPES=[("bug","Bug"),("feature","Feature"),("praise","Praise"),("other","Other")]
    user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    type=models.CharField(max_length=20,choices=TYPES,default="other"); rating=models.IntegerField(null=True,blank=True)
    message=models.TextField(); page_url=models.CharField(max_length=500,blank=True,default="")
    is_read=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: app_label="support"; db_table="support_user_feedback"; ordering=["-created_at"]