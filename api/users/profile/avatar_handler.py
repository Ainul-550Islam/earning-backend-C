"""
api/users/profile/avatar_handler.py
Avatar upload, resize, storage
pip install Pillow
"""
import os
import uuid
import logging
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from ..constants import ProfileConstants
from ..exceptions import UserBaseException

logger = logging.getLogger(__name__)


class AvatarValidationError(UserBaseException):
    default_detail = 'Invalid avatar file.'


class AvatarHandler:

    ALLOWED_TYPES = ProfileConstants.AVATAR_ALLOWED_TYPES
    MAX_SIZE_MB   = ProfileConstants.AVATAR_MAX_SIZE_MB
    DIMENSIONS    = ProfileConstants.AVATAR_DIMENSIONS    # (400, 400)
    UPLOAD_DIR    = 'avatars/'

    def upload(self, user, file_obj) -> str:
        """
        Avatar upload করো।
        Returns: file URL
        """
        self._validate(file_obj)
        processed = self._process(file_obj)
        url = self._save(processed, user.id)
        self._delete_old(user)

        # Update user model
        user.avatar = url
        user.save(update_fields=['avatar'])

        # Cache invalidate করো
        from ..cache import user_cache
        user_cache.invalidate_profile(str(user.id))

        logger.info(f'Avatar uploaded for user: {user.id}')
        return url

    def delete(self, user) -> bool:
        """Avatar delete করো"""
        self._delete_old(user)
        user.avatar = None
        user.save(update_fields=['avatar'])
        return True

    # ─────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────
    def _validate(self, file_obj) -> None:
        # Size check
        max_bytes = self.MAX_SIZE_MB * 1024 * 1024
        if file_obj.size > max_bytes:
            raise AvatarValidationError(
                detail=f'File too large. Max size is {self.MAX_SIZE_MB}MB.'
            )
        # Type check
        content_type = getattr(file_obj, 'content_type', '')
        if content_type not in self.ALLOWED_TYPES:
            raise AvatarValidationError(
                detail=f'Invalid file type. Allowed: JPEG, PNG, WebP.'
            )

    def _process(self, file_obj) -> BytesIO:
        """Resize + compress করো"""
        img    = Image.open(file_obj)
        # RGB convert (PNG alpha channel handle)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        # Crop to square
        img = self._crop_to_square(img)
        # Resize
        img = img.resize(self.DIMENSIONS, Image.LANCZOS)
        # Save
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        return output

    def _crop_to_square(self, img: Image) -> Image:
        """Center crop to square"""
        w, h   = img.size
        min_dim = min(w, h)
        left   = (w - min_dim) // 2
        top    = (h - min_dim) // 2
        return img.crop((left, top, left + min_dim, top + min_dim))

    def _save(self, file_bytes: BytesIO, user_id) -> str:
        filename = f"{self.UPLOAD_DIR}{user_id}_{uuid.uuid4().hex[:8]}.jpg"
        path     = default_storage.save(filename, ContentFile(file_bytes.read()))
        return default_storage.url(path)

    def _delete_old(self, user) -> None:
        """পুরনো avatar delete করো"""
        if not user.avatar:
            return
        try:
            old_path = str(user.avatar)
            if old_path and default_storage.exists(old_path):
                default_storage.delete(old_path)
        except Exception as e:
            logger.warning(f'Old avatar delete failed: {e}')


# Singleton
avatar_handler = AvatarHandler()
