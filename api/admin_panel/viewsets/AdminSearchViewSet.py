# api/admin_panel/viewsets/AdminSearchViewSet.py
"""AdminSearchViewSet — global search across all models."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.utils import timezone

from ..constants import SEARCH_MIN_QUERY_LENGTH, SEARCH_MAX_RESULTS_PER_MODEL
from ..pagination import SearchResultsPagination


class AdminSearchViewSet(viewsets.ViewSet):
    """Global search endpoint across all admin-managed models."""
    permission_classes = [IsAdminUser]
    pagination_class = SearchResultsPagination

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Perform global search.
        ?q=query&model=users.UserProfile&limit=20
        """
        q = request.query_params.get('q', '').strip()
        model_filter = request.query_params.get('model', '')
        limit = min(int(request.query_params.get('limit', SEARCH_MAX_RESULTS_PER_MODEL)), 100)

        if len(q) < SEARCH_MIN_QUERY_LENGTH:
            return Response({
                'error': f'Search query must be at least {SEARCH_MIN_QUERY_LENGTH} characters.',
                'results': [],
            }, status=status.HTTP_400_BAD_REQUEST)

        results = self._perform_search(q, model_filter, limit)

        # Log search
        self._log_search(request, q, model_filter, sum(len(r['items']) for r in results))

        return Response({
            'query': q,
            'model_filter': model_filter,
            'results': results,
            'total': sum(len(r['items']) for r in results),
        })

    def _perform_search(self, q: str, model_filter: str, limit: int) -> list:
        """Run search across registered models."""
        from django.apps import apps
        results = []

        search_registry = [
            {
                'model': 'auth.User',
                'fields': ['username', 'email', 'first_name', 'last_name'],
                'label': 'Users',
            },
            {
                'model': 'admin_panel.SiteContent',
                'fields': ['title', 'identifier', 'content'],
                'label': 'Site Content',
            },
            {
                'model': 'admin_panel.SiteNotification',
                'fields': ['title', 'message'],
                'label': 'Notifications',
            },
            {
                'model': 'admin_panel.SystemConfig',
                'fields': ['key', 'label', 'description'],
                'label': 'System Config',
            },
            {
                'model': 'admin_panel.FeatureFlag',
                'fields': ['flag_key', 'label', 'description'],
                'label': 'Feature Flags',
            },
        ]

        for entry in search_registry:
            model_path = entry['model']
            if model_filter and model_filter.lower() not in model_path.lower():
                continue
            try:
                app_label, model_name = model_path.split('.')
                Model = apps.get_model(app_label, model_name)
                from django.db.models import Q
                query = Q()
                for field in entry['fields']:
                    query |= Q(**{f'{field}__icontains': q})
                items = list(Model.objects.filter(query).values()[:limit])
                # Serialize safely
                safe_items = []
                for item in items:
                    safe = {}
                    for k, v in item.items():
                        if hasattr(v, 'isoformat'):
                            safe[k] = v.isoformat()
                        elif isinstance(v, (str, int, float, bool, type(None))):
                            safe[k] = v
                        else:
                            safe[k] = str(v)
                    safe_items.append(safe)

                if safe_items:
                    results.append({
                        'model': model_path,
                        'label': entry['label'],
                        'count': len(safe_items),
                        'items': safe_items,
                    })
            except Exception:
                pass

        return results

    def _log_search(self, request, q: str, model: str, result_count: int):
        """Log search query to AdminSearch."""
        try:
            from ..models.activity import AdminSearch
            from ..utils import get_client_ip
            AdminSearch.objects.create(
                query=q,
                model=model,
                result_count=result_count,
                user=request.user if request.user.is_authenticated else None,
                ip=get_client_ip(request),
            )
        except Exception:
            pass

    @action(detail=False, methods=['get'])
    def suggestions(self, request):
        """Get search query suggestions from history."""
        q = request.query_params.get('q', '').strip()
        if len(q) < 1:
            return Response({'suggestions': []})
        try:
            from ..models.activity import AdminSearch
            from django.db.models import Count
            suggestions = (
                AdminSearch.objects.filter(
                    query__icontains=q,
                    user=request.user,
                )
                .values('query')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )
            return Response({'suggestions': [s['query'] for s in suggestions]})
        except Exception:
            return Response({'suggestions': []})

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get user's recent search queries."""
        try:
            from ..models.activity import AdminSearch
            searches = AdminSearch.objects.filter(
                user=request.user
            ).order_by('-created_at')[:20]
            return Response({
                'searches': [{'query': s.query, 'created_at': s.created_at.isoformat()} for s in searches]
            })
        except Exception:
            return Response({'searches': []})