# api/cms/services/MenuService.py
"""
MenuService: Build menu trees, CRUD, reorder, cache management.
"""
import logging
from typing import List, Dict, Optional, Any

from django.db import transaction
from django.utils.text import slugify
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MenuService:
    """Service for navigation menu management."""

    @staticmethod
    def get_menu(location: str = None, slug: str = None) -> Optional[Any]:
        """Get menu by location or slug."""
        from api.cms.models_new.menu import Menu
        try:
            if location:
                return Menu.get_by_location(location)
            elif slug:
                return Menu.objects.get(slug=slug, is_active=True)
            return None
        except Exception:
            return None

    @staticmethod
    def build_menu_tree(menu, user=None, role: str = '') -> List[Dict]:
        """Build nested menu tree with visibility filtering."""
        try:
            visibility_context = {
                'user': user,
                'role': role,
                'is_authenticated': user.is_authenticated if user else False,
                'is_staff': getattr(user, 'is_staff', False),
            }
            return menu.build_tree(visibility_context=visibility_context)
        except Exception as e:
            logger.error(f"Error building menu tree for {menu.id}: {e}")
            return []

    @staticmethod
    def create_menu(name: str, location: str, description: str = '', is_active: bool = True) -> Optional[Any]:
        """Create a new menu."""
        from api.cms.models_new.menu import Menu
        try:
            slug = slugify(name)
            counter = 1
            base = slug
            while Menu.objects.filter(slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            return Menu.objects.create(name=name, slug=slug, location=location, description=description, is_active=is_active)
        except Exception as e:
            logger.error(f"Error creating menu: {e}", exc_info=True)
            return None

    @staticmethod
    def create_menu_item(menu, label: str, url: str = '', parent=None, sort_order: int = 0, **kwargs) -> Optional[Any]:
        """Add an item to a menu."""
        from api.cms.models_new.menu import MenuItem
        try:
            item = MenuItem.objects.create(
                menu=menu, label=label, url=url,
                parent=parent, sort_order=sort_order, **kwargs
            )
            menu.invalidate_cache()
            return item
        except Exception as e:
            logger.error(f"Error creating menu item: {e}", exc_info=True)
            return None

    @staticmethod
    def reorder_items(order_data: List[Dict]) -> bool:
        """Bulk reorder menu items. order_data: [{id, sort_order}]"""
        from api.cms.models_new.menu import MenuItem
        try:
            MenuItem.bulk_reorder(order_data)
            return True
        except Exception as e:
            logger.error(f"Error reordering menu items: {e}", exc_info=True)
            return False

    @staticmethod
    def delete_menu_item(item) -> bool:
        """Delete a menu item."""
        try:
            menu = item.menu
            item.delete()
            menu.invalidate_cache()
            return True
        except Exception as e:
            logger.error(f"Error deleting menu item: {e}", exc_info=True)
            return False

    @staticmethod
    def get_all_menus() -> List[Any]:
        """Get all active menus."""
        from api.cms.models_new.menu import Menu
        return list(Menu.objects.filter(is_active=True).order_by('location', 'name'))

    @staticmethod
    def invalidate_all_caches() -> None:
        """Invalidate all menu caches."""
        from api.cms.models_new.menu import Menu
        for menu in Menu.objects.all():
            menu.invalidate_cache()
