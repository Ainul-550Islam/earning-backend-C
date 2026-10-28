from rest_framework import serializers
from api.support.models import KBCategory
class KBCategorySerializer(serializers.ModelSerializer):
    article_count = serializers.SerializerMethodField()
    children      = serializers.SerializerMethodField()
    class Meta:
        model  = KBCategory
        fields = ['id','name','slug','icon','description','parent','sort_order','is_active','article_count','children']
    def get_article_count(self, obj) -> int:
        return obj.articles.filter(status='published',is_public=True).count()
    def get_children(self, obj) -> list:
        return KBCategorySerializer(obj.children.filter(is_active=True), many=True).data