from rest_framework import serializers
from api.support.models import TicketRating
class TicketRatingSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model  = TicketRating
        fields = ['id','ticket','user','username','score','review_text','agent_rating','speed_rating','solution_rating','rated_at']
        read_only_fields = ['rated_at','user']