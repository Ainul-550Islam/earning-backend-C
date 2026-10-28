# api/cms/services/VersioningService.py
"""
VersioningService: Content version history, diff generation, and restore.
"""
import logging
import json
from typing import List, Dict, Optional, Any, Tuple

from django.db import transaction
from django.utils import timezone
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)


class VersioningService:
    """Service for content versioning: history, diff, restore."""

    VERSIONED_FIELDS_PAGE = [
        'title', 'slug', 'subtitle', 'content', 'excerpt',
        'status', 'meta_title', 'meta_description', 'meta_keywords',
        'tags', 'page_type', 'visibility', 'is_featured',
    ]

    VERSIONED_FIELDS_BLOG = [
        'title', 'slug', 'body', 'excerpt', 'status',
        'is_featured', 'allow_comments', 'language',
    ]

    # ────────────────────────────────────────────────────
    # SNAPSHOT
    # ────────────────────────────────────────────────────

    @staticmethod
    def take_snapshot(obj, content_type: str, user=None) -> Optional[Dict]:
        """
        Take a snapshot of current object state.

        Returns:
            Snapshot dict or None
        """
        try:
            fields = {
                'page': VersioningService.VERSIONED_FIELDS_PAGE,
                'blog': VersioningService.VERSIONED_FIELDS_BLOG,
            }.get(content_type, [])

            snapshot = {
                'id': obj.id,
                'version': getattr(obj, 'version', 1),
                'content_type': content_type,
                'taken_at': timezone.now().isoformat(),
                'taken_by': user.id if user else None,
                'data': {
                    field: getattr(obj, field, None)
                    for field in fields
                    if hasattr(obj, field)
                }
            }
            return snapshot
        except Exception as e:
            logger.error(f"Error taking snapshot: {e}", exc_info=True)
            return None

    # ────────────────────────────────────────────────────
    # VERSION HISTORY
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_version_history_page(page) -> List[Dict]:
        """Get version history for a content page."""
        from api.cms.models import ContentPage
        try:
            history = page.get_version_history()
            return [
                {
                    'version': v.version,
                    'id': v.id,
                    'status': v.status,
                    'title': v.title,
                    'created_at': v.created_at,
                    'author': v.author.username if v.author else None,
                }
                for v in history
            ]
        except Exception as e:
            logger.error(f"Error getting version history for page {page.id}: {e}")
            return []

    @staticmethod
    def get_version_history_blog(post) -> List[Dict]:
        """Get version history for a blog post (stored as archived versions)."""
        from api.cms.models_new.blog import BlogPost
        try:
            # Archived versions linked by parent_version (if implemented)
            # For now, return current post info
            return [{
                'version': post.version,
                'id': post.id,
                'status': post.status,
                'title': post.title,
                'created_at': post.created_at,
                'author': post.author.username if post.author else None,
            }]
        except Exception as e:
            logger.error(f"Error getting version history for blog post {post.id}: {e}")
            return []

    # ────────────────────────────────────────────────────
    # DIFF
    # ────────────────────────────────────────────────────

    @staticmethod
    def diff_versions(snapshot_a: Dict, snapshot_b: Dict) -> Dict[str, Any]:
        """
        Compare two snapshots and return differences.

        Args:
            snapshot_a: Earlier snapshot
            snapshot_b: Later snapshot

        Returns:
            Dict with changed fields and their old/new values
        """
        changes = {}
        data_a = snapshot_a.get('data', {})
        data_b = snapshot_b.get('data', {})

        all_keys = set(list(data_a.keys()) + list(data_b.keys()))
        for key in all_keys:
            old_val = data_a.get(key)
            new_val = data_b.get(key)
            if old_val != new_val:
                changes[key] = {
                    'old': old_val,
                    'new': new_val,
                }

        return {
            'version_a': snapshot_a.get('version'),
            'version_b': snapshot_b.get('version'),
            'changes': changes,
            'changed_fields': list(changes.keys()),
            'total_changes': len(changes),
        }

    @staticmethod
    def diff_page_versions(page_a, page_b) -> Dict[str, Any]:
        """Compare two ContentPage version objects."""
        changes = {}
        for field in VersioningService.VERSIONED_FIELDS_PAGE:
            val_a = getattr(page_a, field, None)
            val_b = getattr(page_b, field, None)
            if val_a != val_b:
                changes[field] = {'old': val_a, 'new': val_b}
        return {
            'version_a': page_a.version,
            'version_b': page_b.version,
            'changes': changes,
            'total_changes': len(changes),
        }

    # ────────────────────────────────────────────────────
    # RESTORE
    # ────────────────────────────────────────────────────

    @staticmethod
    def restore_page_version(current_page, target_version_page, user=None) -> bool:
        """
        Restore a content page to a previous version.

        Args:
            current_page: Current ContentPage instance
            target_version_page: The version to restore from
            user: User performing restore

        Returns:
            True on success
        """
        try:
            with transaction.atomic():
                # Save current state as a new archived version first
                old_snapshot = VersioningService.take_snapshot(current_page, 'page', user=user)

                # Restore fields from target version
                for field in VersioningService.VERSIONED_FIELDS_PAGE:
                    if hasattr(target_version_page, field):
                        setattr(current_page, field, getattr(target_version_page, field))

                # Increment version
                current_page.version = (current_page.version or 1) + 1
                current_page.save()

                logger.info(
                    f"Restored page {current_page.id} to version "
                    f"{target_version_page.version} by user {user.id if user else 'system'}"
                )
                return True
        except Exception as e:
            logger.error(f"Error restoring page version: {e}", exc_info=True)
            return False

    @staticmethod
    def restore_blog_version(current_post, snapshot: Dict, user=None) -> bool:
        """
        Restore a blog post from a snapshot.

        Args:
            current_post: BlogPost instance
            snapshot: Snapshot dict from take_snapshot()
            user: User performing restore

        Returns:
            True on success
        """
        try:
            with transaction.atomic():
                data = snapshot.get('data', {})
                for field, value in data.items():
                    if hasattr(current_post, field) and field != 'slug':
                        setattr(current_post, field, value)
                current_post.version = (current_post.version or 1) + 1
                current_post.save()
                logger.info(f"Restored blog post {current_post.id} from snapshot")
                return True
        except Exception as e:
            logger.error(f"Error restoring blog post: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # CREATE NEW VERSION
    # ────────────────────────────────────────────────────

    @staticmethod
    def create_page_version(page) -> Optional[Any]:
        """Create a new draft version of a page."""
        try:
            return page.create_new_version()
        except Exception as e:
            logger.error(f"Error creating page version: {e}", exc_info=True)
            return None
