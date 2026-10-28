# cms/viewsets_new/bulk_operations_mixin.py
"""
Bulk Operations Mixin for ViewSets

Provides bulk CRUD operations (create, update, delete, reorder) to any ViewSet.

Can be mixed into existing ViewSets to add:
- bulk_create: Create multiple items in one request
- bulk_update: Update multiple items with different values
- bulk_delete: Delete multiple items
- bulk_reorder: Reorder items (for models with position field)
- bulk_export: Export all items as JSON/CSV
- bulk_import: Import items from JSON/CSV

Usage:
    class MyViewSet(BulkOperationsMixin, viewsets.ModelViewSet):
        queryset = MyModel.objects.all()
        serializer_class = MySerializer
"""

from rest_framework import status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import transaction
from django.core.exceptions import ValidationError
import logging
import csv
import io
import json
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger('cms.viewsets.bulk_operations')


class BulkOperationsMixin:
    """
    Mixin providing bulk operations to ViewSets
    
    Adds the following actions:
    - POST /resource/bulk-create/
    - PATCH /resource/bulk-update/
    - POST /resource/bulk-delete/
    - POST /resource/bulk-reorder/
    - GET /resource/bulk-export/
    - POST /resource/bulk-import/
    
    All operations:
    - Are transactional (all-or-nothing)
    - Include comprehensive error reporting
    - Support partial success modes
    - Log all operations for audit
    """
    
    # Override these in subclass if needed
    bulk_permission_classes = [IsAdminUser]
    max_bulk_size = 1000
    allow_partial_success = False  # Allow some to fail, others to succeed
    
    # ─────────────────────────────────────────────────────────────────────────
    # BULK CREATE
    # ─────────────────────────────────────────────────────────────────────────
    
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAdminUser],
        url_path='bulk-create'
    )
    def bulk_create(self, request):
        """
        Create multiple items in a single request
        
        Request body:
        {
            "items": [
                {"title": "Item 1", "description": "..."},
                {"title": "Item 2", "description": "..."},
                ...
            ]
        }
        
        Response:
        {
            "created": 10,
            "failed": 0,
            "results": [...],
            "errors": []
        }
        """
        items = request.data.get('items', [])
        
        # Validate request size
        if len(items) == 0:
            return Response(
                {'error': 'items list cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(items) > self.max_bulk_size:
            return Response(
                {'error': f'Maximum {self.max_bulk_size} items per request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_objects = []
        errors = []
        
        # Use transaction for consistency
        try:
            with transaction.atomic():
                for idx, item_data in enumerate(items):
                    try:
                        serializer = self.get_serializer(data=item_data)
                        serializer.is_valid(raise_exception=True)
                        
                        # Add any defaults (e.g., created_by user)
                        if hasattr(serializer, 'save'):
                            obj = serializer.save()
                        else:
                            obj = serializer.validated_data
                        
                        created_objects.append(serializer.data)
                        logger.info(f"Bulk created item {idx + 1}/{len(items)}")
                        
                    except serializers.ValidationError as e:
                        error_entry = {
                            'index': idx,
                            'item': item_data,
                            'error': str(e.detail),
                        }
                        errors.append(error_entry)
                        
                        if not self.allow_partial_success:
                            raise
                    
                    except Exception as e:
                        error_entry = {
                            'index': idx,
                            'item': item_data,
                            'error': str(e),
                        }
                        errors.append(error_entry)
                        logger.error(f"Bulk create error at index {idx}: {e}")
                        
                        if not self.allow_partial_success:
                            raise
        
        except Exception as e:
            logger.error(f"Bulk create transaction failed: {e}")
            return Response(
                {
                    'error': 'Bulk create failed',
                    'details': str(e),
                    'created': len(created_objects),
                    'errors': errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'created': len(created_objects),
            'failed': len(errors),
            'results': created_objects,
            'errors': errors,
        }, status=status.HTTP_201_CREATED)
    
    # ─────────────────────────────────────────────────────────────────────────
    # BULK UPDATE
    # ─────────────────────────────────────────────────────────────────────────
    
    @action(
        detail=False,
        methods=['patch'],
        permission_classes=[IsAdminUser],
        url_path='bulk-update'
    )
    def bulk_update(self, request):
        """
        Update multiple items with potentially different values
        
        Request body:
        {
            "items": [
                {"id": 1, "title": "Updated Title", "field": "value"},
                {"id": 2, "status": "active"},
                ...
            ]
        }
        
        Response:
        {
            "updated": 10,
            "failed": 0,
            "results": [...],
            "errors": []
        }
        """
        items = request.data.get('items', [])
        
        if len(items) == 0:
            return Response(
                {'error': 'items list cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(items) > self.max_bulk_size:
            return Response(
                {'error': f'Maximum {self.max_bulk_size} items per request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_objects = []
        errors = []
        
        try:
            with transaction.atomic():
                for idx, item_data in enumerate(items):
                    try:
                        # Get ID
                        item_id = item_data.get('id')
                        if not item_id:
                            raise ValidationError("Each item must have an 'id' field")
                        
                        # Get object
                        obj = self.get_queryset().get(pk=item_id)
                        
                        # Update with provided fields
                        serializer = self.get_serializer(
                            obj,
                            data=item_data,
                            partial=True
                        )
                        serializer.is_valid(raise_exception=True)
                        serializer.save()
                        
                        updated_objects.append(serializer.data)
                        logger.info(f"Bulk updated item {idx + 1}/{len(items)}")
                        
                    except Exception as e:
                        error_entry = {
                            'index': idx,
                            'item_id': item_data.get('id'),
                            'error': str(e),
                        }
                        errors.append(error_entry)
                        logger.error(f"Bulk update error at index {idx}: {e}")
                        
                        if not self.allow_partial_success:
                            raise
        
        except Exception as e:
            logger.error(f"Bulk update transaction failed: {e}")
            return Response(
                {
                    'error': 'Bulk update failed',
                    'details': str(e),
                    'updated': len(updated_objects),
                    'errors': errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'updated': len(updated_objects),
            'failed': len(errors),
            'results': updated_objects,
            'errors': errors,
        }, status=status.HTTP_200_OK)
    
    # ─────────────────────────────────────────────────────────────────────────
    # BULK DELETE
    # ─────────────────────────────────────────────────────────────────────────
    
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAdminUser],
        url_path='bulk-delete'
    )
    def bulk_delete(self, request):
        """
        Soft-delete or hard-delete multiple items
        
        Request body:
        {
            "ids": [1, 2, 3, ...],
            "soft_delete": true  (optional, default=true)
        }
        
        Response:
        {
            "deleted": 10,
            "failed": 0,
            "errors": []
        }
        """
        ids = request.data.get('ids', [])
        soft_delete = request.data.get('soft_delete', True)
        
        if len(ids) == 0:
            return Response(
                {'error': 'ids list cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(ids) > self.max_bulk_size:
            return Response(
                {'error': f'Maximum {self.max_bulk_size} items per request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deleted_count = 0
        errors = []
        
        try:
            with transaction.atomic():
                for idx, item_id in enumerate(ids):
                    try:
                        obj = self.get_queryset().get(pk=item_id)
                        
                        if soft_delete and hasattr(obj, 'is_active'):
                            # Soft delete
                            obj.is_active = False
                            obj.save(update_fields=['is_active'])
                        else:
                            # Hard delete
                            obj.delete()
                        
                        deleted_count += 1
                        logger.info(f"Bulk deleted item {idx + 1}/{len(ids)}")
                        
                    except Exception as e:
                        error_entry = {
                            'index': idx,
                            'id': item_id,
                            'error': str(e),
                        }
                        errors.append(error_entry)
                        logger.error(f"Bulk delete error for id {item_id}: {e}")
                        
                        if not self.allow_partial_success:
                            raise
        
        except Exception as e:
            logger.error(f"Bulk delete transaction failed: {e}")
            return Response(
                {
                    'error': 'Bulk delete failed',
                    'details': str(e),
                    'deleted': deleted_count,
                    'errors': errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'deleted': deleted_count,
            'failed': len(errors),
            'errors': errors,
        }, status=status.HTTP_200_OK)
    
    # ─────────────────────────────────────────────────────────────────────────
    # BULK REORDER
    # ─────────────────────────────────────────────────────────────────────────
    
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAdminUser],
        url_path='bulk-reorder'
    )
    def bulk_reorder(self, request):
        """
        Reorder multiple items by position
        
        Request body:
        {
            "items": [
                {"id": 1, "position": 0},
                {"id": 2, "position": 1},
                {"id": 3, "position": 2},
                ...
            ]
        }
        
        Response:
        {
            "reordered": 10,
            "failed": 0,
            "errors": []
        }
        """
        items = request.data.get('items', [])
        
        if len(items) == 0:
            return Response(
                {'error': 'items list cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if model supports position field
        if not self._supports_ordering():
            return Response(
                {'error': 'Model does not support ordering'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reordered_count = 0
        errors = []
        
        try:
            with transaction.atomic():
                for idx, item_data in enumerate(items):
                    try:
                        item_id = item_data.get('id')
                        position = item_data.get('position')
                        
                        if item_id is None or position is None:
                            raise ValidationError("Each item needs 'id' and 'position'")
                        
                        obj = self.get_queryset().get(pk=item_id)
                        obj.position = position
                        obj.save(update_fields=['position'])
                        
                        reordered_count += 1
                        logger.info(f"Reordered item {idx + 1}/{len(items)}")
                        
                    except Exception as e:
                        error_entry = {
                            'index': idx,
                            'id': item_data.get('id'),
                            'error': str(e),
                        }
                        errors.append(error_entry)
                        
                        if not self.allow_partial_success:
                            raise
        
        except Exception as e:
            logger.error(f"Bulk reorder failed: {e}")
            return Response(
                {
                    'error': 'Bulk reorder failed',
                    'details': str(e),
                    'reordered': reordered_count,
                    'errors': errors,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'reordered': reordered_count,
            'failed': len(errors),
            'errors': errors,
        }, status=status.HTTP_200_OK)
    
    # ─────────────────────────────────────────────────────────────────────────
    # BULK EXPORT
    # ─────────────────────────────────────────────────────────────────────────
    
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAdminUser],
        url_path='bulk-export'
    )
    def bulk_export(self, request):
        """
        Export all items (or filtered) as JSON
        
        Query parameters:
        - format: "json" or "csv" (default: json)
        - filters: Optional query params to filter export
        
        Response:
        {
            "count": 100,
            "format": "json",
            "data": [...]
        }
        """
        export_format = request.query_params.get('format', 'json')
        
        # Get queryset (with any filters applied)
        queryset = self.filter_queryset(self.get_queryset())
        
        if export_format == 'json':
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'count': queryset.count(),
                'format': 'json',
                'data': serializer.data,
            })
        
        elif export_format == 'csv':
            serializer = self.get_serializer(queryset, many=True)
            
            # Build CSV
            output = io.StringIO()
            if queryset.exists():
                first_item = serializer.data[0]
                writer = csv.DictWriter(output, fieldnames=first_item.keys())
                writer.writeheader()
                writer.writerows(serializer.data)
            
            return Response({
                'count': queryset.count(),
                'format': 'csv',
                'data': output.getvalue(),
            })
        
        else:
            return Response(
                {'error': f'Unsupported format: {export_format}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # ─────────────────────────────────────────────────────────────────────────
    # BULK IMPORT
    # ─────────────────────────────────────────────────────────────────────────
    
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAdminUser],
        url_path='bulk-import'
    )
    def bulk_import(self, request):
        """
        Import multiple items from JSON
        
        Request body:
        {
            "items": [...],
            "mode": "create"  (or "update", "upsert")
        }
        
        Response:
        {
            "imported": 10,
            "failed": 0,
            "errors": []
        }
        """
        items = request.data.get('items', [])
        mode = request.data.get('mode', 'create')
        
        if len(items) == 0:
            return Response(
                {'error': 'items list cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if mode not in ('create', 'update', 'upsert'):
            return Response(
                {'error': f'Invalid mode: {mode}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delegate to appropriate method
        if mode == 'create':
            return self._bulk_import_create(items)
        elif mode == 'update':
            return self._bulk_import_update(items)
        elif mode == 'upsert':
            return self._bulk_import_upsert(items)
    
    def _bulk_import_create(self, items: List[Dict]) -> Response:
        """Import as new items (create)"""
        return self.bulk_create(type('obj', (object,), {'data': {'items': items}})())
    
    def _bulk_import_update(self, items: List[Dict]) -> Response:
        """Import as updates (update)"""
        return self.bulk_update(type('obj', (object,), {'data': {'items': items}})())
    
    def _bulk_import_upsert(self, items: List[Dict]) -> Response:
        """Import as upsert (create or update)"""
        # Implementation depends on model's unique field
        # Default: try update, create if not found
        imported = 0
        errors = []
        
        for item in items:
            try:
                if 'id' in item:
                    # Try to update
                    obj = self.get_queryset().get(pk=item['id'])
                    serializer = self.get_serializer(obj, data=item, partial=True)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                else:
                    # Create new
                    serializer = self.get_serializer(data=item)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                
                imported += 1
            except Exception as e:
                errors.append({'item': item, 'error': str(e)})
        
        return Response({
            'imported': imported,
            'failed': len(errors),
            'errors': errors,
        }, status=status.HTTP_200_OK)
    
    # ─────────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _supports_ordering(self) -> bool:
        """Check if model supports ordering (has 'position' field)"""
        queryset = self.get_queryset()
        model = queryset.model
        return hasattr(model, 'position')


# ─────────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLES
# ─────────────────────────────────────────────────────────────────────────────

"""
Example 1: Add to existing ViewSet

from api.cms.viewsets_new.bulk_operations_mixin import BulkOperationsMixin

class BlogPostViewSet(BulkOperationsMixin, viewsets.ModelViewSet):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer
    
    # Optional: customize bulk settings
    max_bulk_size = 500
    allow_partial_success = True

# Now available endpoints:
# POST /api/v3/blog-posts/bulk-create/
# PATCH /api/v3/blog-posts/bulk-update/
# POST /api/v3/blog-posts/bulk-delete/
# POST /api/v3/blog-posts/bulk-reorder/
# GET /api/v3/blog-posts/bulk-export/
# POST /api/v3/blog-posts/bulk-import/


Example 2: Bulk create request

POST /api/v3/blog-posts/bulk-create/
{
    "items": [
        {"title": "Post 1", "content": "Content 1"},
        {"title": "Post 2", "content": "Content 2"},
        {"title": "Post 3", "content": "Content 3"}
    ]
}

Response:
{
    "created": 3,
    "failed": 0,
    "results": [...],
    "errors": []
}


Example 3: Bulk update request

PATCH /api/v3/blog-posts/bulk-update/
{
    "items": [
        {"id": 1, "status": "published"},
        {"id": 2, "status": "draft"},
        {"id": 3, "featured": true}
    ]
}

Response:
{
    "updated": 3,
    "failed": 0,
    "results": [...],
    "errors": []
}


Example 4: Bulk reorder request

POST /api/v3/categories/bulk-reorder/
{
    "items": [
        {"id": 5, "position": 0},
        {"id": 3, "position": 1},
        {"id": 7, "position": 2},
        {"id": 1, "position": 3}
    ]
}

Response:
{
    "reordered": 4,
    "failed": 0,
    "errors": []
}
"""
