from rest_framework import serializers
from api.support.models import ChatTranscript
class ChatTranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ChatTranscript
        fields = ['id','session','content_html','content_text','generated_at','emailed_at','email_sent_to']