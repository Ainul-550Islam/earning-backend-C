# api/djoyalty/atachment_upload_view.py
"""
Djoyalty Attachment Upload View -- File upload for receipt scans, avatars।
Handles: receipt images, customer avatars, catalog item images।
Supports: local storage + S3 (via django-storages)।
"""
import logging
import os
import uuid
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'heic', 'pdf'}
MAX_FILE_SIZE_MB = 10


class ReceiptUploadView(APIView):
    """
    POST /api/loyalty/upload/receipt/
    Upload receipt image -> start OCR processing।

    Form data:
        receipt: (file) -- image file
        customer_id: (int) -- customer ID

    Returns: { receipt_url, scan_id, status }
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('receipt')
        customer_id = request.data.get('customer_id')

        if not file:
            return Response({'error': 'No file uploaded.'}, status=400)

        if not customer_id:
            return Response({'error': 'customer_id required.'}, status=400)

        # Validate
        error = self._validate_file(file)
        if error:
            return Response({'error': error}, status=400)

        # Get customer
        try:
            from .models.core import Customer
            customer = Customer.objects.get(id=customer_id, is_active=True)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found.'}, status=404)

        # Save file
        try:
            file_url = self._save_file(file, folder='receipts', customer_code=customer.code)
        except Exception as e:
            logger.error('ReceiptUploadView: file save error: %s', e)
            return Response({'error': 'File upload failed.'}, status=500)

        # Create ReceiptScan record
        try:
            from .models.family_eco import ReceiptScan
            scan = ReceiptScan.objects.create(
                customer=customer,
                tenant=customer.tenant,
                receipt_image_url=file_url,
                status='pending',
            )

            # Queue OCR processing
            try:
                from .tasks.receipt_scan_tasks import process_receipt_scan_task
                process_receipt_scan_task.delay(scan_id=scan.id)
            except Exception:
                pass

            return Response({
                'success': True,
                'receipt_url': file_url,
                'scan_id': scan.id,
                'status': 'pending',
                'message': 'Receipt uploaded. OCR processing started.',
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error('ReceiptUploadView: scan creation error: %s', e)
            return Response({'error': 'Could not create scan record.'}, status=500)

    @staticmethod
    def _validate_file(file) -> str:
        """Validate file -- returns error string or empty string."""
        ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
        if ext not in ALLOWED_EXTENSIONS:
            return f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'

        size_mb = file.size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return f'File too large. Max {MAX_FILE_SIZE_MB}MB allowed.'

        return ''

    @staticmethod
    def _save_file(file, folder: str = 'uploads', customer_code: str = '') -> str:
        """Save file to storage -- local or S3।"""
        ext = file.name.rsplit('.', 1)[-1].lower()
        filename = f'{customer_code}_{uuid.uuid4().hex}.{ext}'
        relative_path = f'djoyalty/{folder}/{filename}'

        # Try S3 via django-storages
        try:
            from storages.backends.s3boto3 import S3Boto3Storage
            storage = S3Boto3Storage()
            path = storage.save(relative_path, file)
            return storage.url(path)
        except ImportError:
            pass

        # Local storage fallback
        media_root = getattr(settings, 'MEDIA_ROOT', '/tmp')
        local_dir = os.path.join(media_root, 'djoyalty', folder)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, filename)

        with open(local_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        return f'{media_url}djoyalty/{folder}/{filename}'


class CustomerAvatarUploadView(APIView):
    """
    POST /api/loyalty/upload/avatar/
    Upload customer avatar/profile image।
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('avatar')
        customer_id = request.data.get('customer_id')

        if not file or not customer_id:
            return Response({'error': 'avatar file and customer_id required.'}, status=400)

        error = ReceiptUploadView._validate_file(file)
        if error:
            return Response({'error': error}, status=400)

        try:
            from .models.core import Customer
            customer = Customer.objects.get(id=customer_id, is_active=True)
            url = ReceiptUploadView._save_file(file, folder='avatars',
                                                customer_code=customer.code)
            if hasattr(customer, 'avatar_url'):
                customer.avatar_url = url
                customer.save(update_fields=['avatar_url'])

            return Response({'success': True, 'avatar_url': url})
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found.'}, status=404)
        except Exception as e:
            logger.error('CustomerAvatarUploadView error: %s', e)
            return Response({'error': 'Upload failed.'}, status=500)


class CatalogItemImageUploadView(APIView):
    """
    POST /api/loyalty/upload/catalog-image/
    Upload image for a reward catalog item (admin only)।
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('image')
        item_id = request.data.get('item_id')

        if not file:
            return Response({'error': 'image file required.'}, status=400)

        error = ReceiptUploadView._validate_file(file)
        if error:
            return Response({'error': error}, status=400)

        try:
            url = ReceiptUploadView._save_file(file, folder='catalog', customer_code='item')
            if item_id:
                from .models.catalog import RewardCatalogItem
                RewardCatalogItem.objects.filter(id=item_id).update(image_url=url)
            return Response({'success': True, 'image_url': url})
        except Exception as e:
            logger.error('CatalogItemImageUploadView error: %s', e)
            return Response({'error': 'Upload failed.'}, status=500)
