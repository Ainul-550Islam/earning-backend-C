from rest_framework import serializers
from api.support.models import KBArticle
class KBArticleListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    helpful_ratio = serializers.SerializerMethodField()
    class Meta:
        model  = KBArticle
        fields = ['id','title','slug','summary','category','category_name','status','is_public','views_count','helpful_yes','helpful_no','helpful_ratio','tags','created_at']
    def get_helpful_ratio(self, obj) -> float:
        t = obj.helpful_yes + obj.helpful_no
        return round(obj.helpful_yes/t*100,1) if t else 0

class KBArticleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    author_name   = serializers.CharField(source='author.username', read_only=True)
    helpful_ratio = serializers.SerializerMethodField()
    class Meta:
        model  = KBArticle
        fields = ['id','title','slug','body','summary','category','category_name','author','author_name','status','is_public','tags','views_count','helpful_yes','helpful_no','helpful_ratio','created_at','updated_at']
        read_only_fields = ['created_at','updated_at','views_count','helpful_yes','helpful_no']
    def get_helpful_ratio(self, obj) -> float:
        t = obj.helpful_yes + obj.helpful_no
        return round(obj.helpful_yes/t*100,1) if t else 0