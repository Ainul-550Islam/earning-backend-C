from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/MediaFileViewSet.py
"""
MediaFileViewSet: Upload, list, delete, tag media files.
MediaFolderViewSet: Folder CRUD.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

logger = logging.getLogger(__name__)


class MediaFileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for media file management.

    Endpoints:
        GET    /api/cms/media/                      - List files
        POST   /api/cms/media/                      - Upload file
        GET    /api/cms/media/{id}/                 - File detail
        PATCH  /api/cms/media/{id}/                 - Update metadata
        DELETE /api/cms/media/{id}/                 - Delete file
        POST   /api/cms/media/{id}/add_tags/        - Add tags
        POST   /api/cms/media/{id}/generate_variants/ - Generate image variants
        POST   /api/cms/media/{id}/push_cdn/        - Push to CDN
        GET    /api/cms/media/statistics/           - Storage stats
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'filename', 'alt_text', 'description']
    ordering_fields = ['created_at', 'size_bytes', 'download_count', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.media import MediaFile
        qs = MediaFile.objects.filter(is_active=True).select_related('folder', 'uploaded_by').prefetch_related('tags')
        # Admin sees all; others see public only
        if not self.request.user.is_staff:
            qs = qs.filter(is_public=True)
        # Folder filter
        folder_id = self.request.query_params.get('folder')
        if folder_id:
            qs = qs.filter(folder_id=folder_id)
        # Type filter
        file_type = self.request.query_params.get('type')
        if file_type:
            qs = qs.filter(file_type=file_type)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers import MediaFileSerializer
        return MediaFileSerializer

    def create(self, request, *args, **kwargs):
        """Upload a media file."""
        from api.cms.services_new.MediaService import MediaService
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        folder_id = request.data.get('folder')
        folder = None
        if folder_id:
            from api.cms.models_new.media import MediaFolder
            try:
                folder = MediaFolder.objects.get(id=folder_id)
            except MediaFolder.DoesNotExist:
                pass
        tag_names = request.data.getlist('tags', [])
        tags = [MediaService.get_or_create_tag(name) for name in tag_names if name]
        media_file = MediaService.upload_file(
            file=file,
            uploaded_by=request.user,
            folder=folder,
            title=request.data.get('title', ''),
            alt_text=request.data.get('alt_text', ''),
            description=request.data.get('description', ''),
            tags=tags,
            is_public=request.data.get('is_public', 'true').lower() == 'true',
        )
        if media_file:
            serializer = self.get_serializer(media_file)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Upload failed'}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Update file metadata."""
        from api.cms.services_new.MediaService import MediaService
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        success = MediaService.update_file_metadata(instance, request.data.dict() if hasattr(request.data, 'dict') else dict(request.data))
        if success:
            return Response(self.get_serializer(instance).data)
        return Response({'error': 'Update failed'}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """Delete a media file."""
        from api.cms.services_new.MediaService import MediaService
        instance = self.get_object()
        hard = request.query_params.get('hard', 'false').lower() == 'true'
        if hard and not request.user.is_staff:
            return Response({'error': 'Admin required for hard delete'}, status=status.HTTP_403_FORBIDDEN)
        MediaService.delete_file(instance, hard_delete=hard)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def add_tags(self, request, pk=None):
        """Add tags to a media file."""
        from api.cms.services_new.MediaService import MediaService
        instance = self.get_object()
        tag_names = request.data.get('tags', [])
        if not tag_names:
            return Response({'error': 'No tags provided'}, status=status.HTTP_400_BAD_REQUEST)
        success = MediaService.add_tags_to_file(instance, tag_names)
        if success:
            return Response({'tags': [t.name for t in instance.tags.all()]})
        return Response({'error': 'Failed to add tags'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def generate_variants(self, request, pk=None):
        """Generate image variants."""
        from api.cms.services_new.MediaVariantService import MediaVariantService
        instance = self.get_object()
        if instance.file_type != 'image':
            return Response({'error': 'Only images support variants'}, status=status.HTTP_400_BAD_REQUEST)
        results = MediaVariantService.generate_all_variants(instance)
        return Response({'variants': results})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def push_cdn(self, request, pk=None):
        """Push file to CDN."""
        from api.cms.services_new.MediaService import MediaService
        instance = self.get_object()
        success = MediaService.push_to_cdn(instance)
        if success:
            return Response({'cdn_url': instance.cdn_url})
        return Response({'error': 'CDN push failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get storage statistics."""
        from api.cms.services_new.MediaService import MediaService
        return Response(MediaService.get_storage_statistics())


class MediaFolderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for media folder management.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'path']

    def get_queryset(self):
        from api.cms.models_new.media import MediaFolder
        return MediaFolder.objects.filter(is_active=True).select_related('parent', 'created_by')

    def get_serializer_class(self):
        from api.cms.serializers import MediaFolderSerializer
        return MediaFolderSerializer

    def create(self, request, *args, **kwargs):
        """Create a new folder."""
        from api.cms.services_new.MediaService import MediaService
        parent_id = request.data.get('parent')
        parent = None
        if parent_id:
            from api.cms.models_new.media import MediaFolder
            try:
                parent = MediaFolder.objects.get(id=parent_id)
            except MediaFolder.DoesNotExist:
                pass
        folder = MediaService.create_folder(
            name=request.data.get('name', ''),
            parent=parent,
            created_by=request.user,
            is_public=request.data.get('is_public', False),
        )
        if folder:
            return Response(self.get_serializer(folder).data, status=status.HTTP_201_CREATED)
        return Response({'error': 'Folder creation failed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get full folder tree."""
        from api.cms.services_new.MediaService import MediaService
        return Response(MediaService.get_folder_tree())
