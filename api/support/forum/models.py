"""api/support/forum/models.py"""
from django.db import models
from django.conf import settings

class ForumQuestion(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE); title=models.CharField(max_length=500)
    body=models.TextField(); category=models.CharField(max_length=50,default="general",db_index=True)
    tags=models.JSONField(default=list); votes=models.IntegerField(default=0,db_index=True)
    answer_count=models.IntegerField(default=0); solved=models.BooleanField(default=False)
    is_active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: app_label="support"; db_table="support_forum_question"; ordering=["-votes","-created_at"]
    def __str__(self): return self.title

class ForumAnswer(models.Model):
    question=models.ForeignKey(ForumQuestion,on_delete=models.CASCADE,related_name="answers")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    body=models.TextField(); votes=models.IntegerField(default=0)
    is_accepted=models.BooleanField(default=False); is_kb_auto=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: app_label="support"; db_table="support_forum_answer"