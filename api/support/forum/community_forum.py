"""api/support/forum/community_forum.py FILE 18"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
logger = logging.getLogger(__name__)

class CommunityForum:
    def list_questions(self, category=None, limit=20, sort="votes") -> list:
        try:
            from api.support.forum.models import ForumQuestion
            qs = ForumQuestion.objects.filter(is_active=True)
            if category: qs = qs.filter(category=category)
            qs = qs.order_by("-votes","-created_at") if sort=="votes" else qs.order_by("-created_at")
            return list(qs[:limit].values("id","title","category","votes","answer_count","solved","created_at","user__username"))
        except: return []

    def ask(self, user, data: dict) -> dict:
        try:
            from api.support.forum.models import ForumQuestion
            q = ForumQuestion.objects.create(user=user, title=data.get("title",""), body=data.get("body",""), category=data.get("category","general"), tags=data.get("tags",[]))
            kb = []
            try:
                from api.support.services.knowledge_base.KBSearchService import kb_search_service
                kb = kb_search_service.search(data.get("title",""), limit=3)
            except: pass
            return {"id":q.id,"title":q.title,"kb_suggestions":kb}
        except Exception as e: return {"error":str(e)}

    def answer(self, user, question_id: int, body: str) -> dict:
        try:
            from api.support.forum.models import ForumQuestion, ForumAnswer
            q = ForumQuestion.objects.get(id=question_id)
            a = ForumAnswer.objects.create(question=q, user=user, body=body)
            ForumQuestion.objects.filter(id=question_id).update(answer_count=__import__("django.db.models",fromlist=["F"]).F("answer_count")+1)
            return {"id":a.id}
        except Exception as e: return {"error":str(e)}

    def upvote(self, question_id: int) -> bool:
        try:
            from api.support.forum.models import ForumQuestion
            from django.db.models import F
            ForumQuestion.objects.filter(id=question_id).update(votes=F("votes")+1)
            return True
        except: return False

community_forum = CommunityForum()

@api_view(["GET"])
@api_view(["POST"])
@permission_classes([AllowAny])
def forum_list(request):
    cat = request.query_params.get("category")
    return Response({"success":True,"questions":community_forum.list_questions(cat)})

@permission_classes([IsAuthenticated])
def ask_question(request):
    r = community_forum.ask(request.user, request.data)
    return Response({"success":"error" not in r,**r}, status=201 if "error" not in r else 400)
@permission_classes([IsAuthenticated])
def answer_question(request, question_id):
    r = community_forum.answer(request.user, question_id, request.data.get("body",""))
    return Response({"success":"error" not in r,**r}, status=201 if "error" not in r else 400)