# api/cms/models/menu.py
"""
Menu models: Menu, MenuItem, MenuVisibility, LandingSection
Full production-ready with tree building, drag-drop reorder, caching.
"""
import uuid
import logging
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from core.models import TimeStampedModel

logger = logging.getLogger(__name__)


def default_dict():
    return {}


def default_list():
    return []


# ─────────────────────────────────────────────
# Menu
# ─────────────────────────────────────────────

class Menu(TimeStampedModel):
    """Navigation menu definition (header, footer, sidebar, etc.)."""

    LOCATION_CHOICES = [
        ('header', _('Header')),
        ('footer', _('Footer')),
        ('sidebar', _('Sidebar')),
        ('mobile', _('Mobile Navigation')),
        ('dashboard', _('Dashboard')),
        ('app_tab', _('App Tab Bar')),
        ('breadcrumb', _('Breadcrumb')),
        ('social', _('Social Links')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Menu Name"), max_length=200)
    slug = models.SlugField(_("Slug"), max_length=200, unique=True)
    location = models.CharField(
        _("Location"), max_length=30,
        choices=LOCATION_CHOICES, default='header',
        db_index=True
    )
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    is_locked = models.BooleanField(
        _("Locked"), default=False,
        help_text=_("If locked, non-admins cannot edit")
    )
    # Cache key version for invalidation
    cache_version = models.PositiveIntegerField(_("Cache Version"), default=1)

    class Meta:
        app_label = "cms"
        verbose_name = _("Menu")
        verbose_name_plural = _("Menus")
        ordering = ['location', 'name']
        indexes = [
            models.Index(fields=['location', 'is_active']),
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_location_display()})"

    def save(self, *args, **kwargs):
        # Bump cache version to invalidate cached menu trees
        if self.pk:
            self.cache_version = (self.cache_version % 9999) + 1
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def invalidate_cache(self):
        """Invalidate all cached representations of this menu."""
        cache.delete(f'menu_{self.slug}')
        cache.delete(f'menu_{self.id}')
        cache.delete(f'menu_location_{self.location}')

    def build_tree(self, visibility_context=None):
        """
        Build a full nested menu tree.
        visibility_context: dict with user role, is_authenticated, etc.
        """
        cache_key = f'menu_tree_{self.id}_v{self.cache_version}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        top_items = self.items.filter(
            parent__isnull=True, is_active=True
        ).order_by('sort_order').select_related('menu')

        tree = [self._build_item_node(item, visibility_context) for item in top_items]
        cache.set(cache_key, tree, 3600)
        return tree

    def _build_item_node(self, item, visibility_context=None):
        """Recursively build menu item node."""
        children = item.children.filter(is_active=True).order_by('sort_order')
        node = {
            'id': item.id,
            'uuid': str(item.uuid),
            'label': item.label,
            'url': item.url,
            'icon': item.icon,
            'sort_order': item.sort_order,
            'open_in_new_tab': item.open_in_new_tab,
            'is_active': item.is_active,
            'css_class': item.css_class,
            'children': [self._build_item_node(child, visibility_context) for child in children]
        }
        return node

    def get_active_items(self):
        """Get all active menu items."""
        return self.items.filter(is_active=True).order_by('sort_order')

    @classmethod
    def get_by_location(cls, location):
        """Get active menu for a location."""
        cache_key = f'menu_location_{location}'
        menu = cache.get(cache_key)
        if menu is None:
            try:
                menu = cls.objects.get(location=location, is_active=True)
                cache.set(cache_key, menu, 3600)
            except cls.DoesNotExist:
                return None
            except cls.MultipleObjectsReturned:
                menu = cls.objects.filter(location=location, is_active=True).first()
                cache.set(cache_key, menu, 3600)
        return menu


# ─────────────────────────────────────────────
# MenuItem
# ─────────────────────────────────────────────

class MenuItem(TimeStampedModel):
    """Individual menu item with nesting, icons, and ordering."""

    LINK_TYPE_CHOICES = [
        ('url', _('Custom URL')),
        ('page', _('CMS Page')),
        ('category', _('Category')),
        ('blog', _('Blog Post')),
        ('external', _('External Link')),
        ('anchor', _('Anchor (#)')),
        ('none', _('No Link')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    menu = models.ForeignKey(
        Menu, on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Menu")
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children',
        verbose_name=_("Parent Item")
    )
    label = models.CharField(_("Label"), max_length=200)
    url = models.CharField(
        _("URL"), max_length=1000, blank=True,
        help_text=_("Relative or absolute URL")
    )
    link_type = models.CharField(
        _("Link Type"), max_length=20,
        choices=LINK_TYPE_CHOICES, default='url'
    )
    icon = models.CharField(
        _("Icon"), max_length=100, blank=True,
        help_text=_("CSS class for icon, e.g. 'fa fa-home'")
    )
    image = models.ImageField(
        _("Image"), upload_to='menu/items/%Y/%m/',
        blank=True, null=True
    )
    sort_order = models.IntegerField(_("Sort Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)
    open_in_new_tab = models.BooleanField(_("Open in New Tab"), default=False)
    is_featured = models.BooleanField(
        _("Featured"), default=False,
        help_text=_("Highlight this item visually")
    )
    css_class = models.CharField(
        _("CSS Class"), max_length=200, blank=True,
        help_text=_("Additional CSS classes for styling")
    )
    rel = models.CharField(
        _("Rel Attribute"), max_length=100, blank=True,
        help_text=_("e.g. nofollow, sponsored")
    )
    # Related object references (optional)
    related_object_type = models.CharField(
        _("Related Object Type"), max_length=100, blank=True
    )
    related_object_id = models.PositiveIntegerField(
        _("Related Object ID"), null=True, blank=True
    )
    # Mega menu content
    has_mega_menu = models.BooleanField(_("Has Mega Menu"), default=False)
    mega_menu_content = models.JSONField(
        _("Mega Menu Content"), default=default_dict, blank=True
    )
    # Click tracking
    click_count = models.PositiveIntegerField(_("Click Count"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Menu Item")
        verbose_name_plural = _("Menu Items")
        ordering = ['menu', 'sort_order']
        indexes = [
            models.Index(fields=['menu', 'parent', 'sort_order']),
            models.Index(fields=['is_active', 'menu']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        depth_prefix = '— ' * self.depth
        return f"{depth_prefix}{self.label}"

    def clean(self):
        if self.parent and self.parent.menu != self.menu:
            raise ValidationError(_("Parent item must belong to the same menu."))
        if self.parent and self.parent == self:
            raise ValidationError(_("A menu item cannot be its own parent."))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate menu cache
        if self.menu:
            self.menu.invalidate_cache()

    @property
    def depth(self):
        """Calculate nesting depth."""
        d = 0
        current = self.parent
        while current:
            d += 1
            current = current.parent
        return d

    def get_full_url(self):
        """Get computed URL."""
        if self.url:
            return self.url
        return '#'

    def record_click(self):
        """Atomically record a click."""
        MenuItem.objects.filter(id=self.id).update(click_count=F('click_count') + 1)
        self.refresh_from_db()

    def reorder(self, new_order):
        """Update sort order."""
        self.sort_order = new_order
        self.save(update_fields=['sort_order'])

    def move_to_parent(self, new_parent):
        """Move item to a new parent."""
        if new_parent and new_parent.menu != self.menu:
            raise ValueError("New parent must be in the same menu")
        self.parent = new_parent
        self.save(update_fields=['parent'])

    @classmethod
    def bulk_reorder(cls, order_data):
        """
        Bulk reorder items.
        order_data: list of {id: int, sort_order: int}
        """
        with transaction.atomic():
            for item_data in order_data:
                cls.objects.filter(id=item_data['id']).update(
                    sort_order=item_data['sort_order']
                )


# ─────────────────────────────────────────────
# MenuVisibility
# ─────────────────────────────────────────────

class MenuVisibility(TimeStampedModel):
    """Controls who can see a menu item."""

    VISIBILITY_CHOICES = [
        ('all', _('All Users')),
        ('logged_in', _('Logged In Users')),
        ('logged_out', _('Logged Out Users')),
        ('role', _('Specific Role')),
        ('staff', _('Staff Only')),
        ('superuser', _('Superuser Only')),
        ('vip', _('VIP Users')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE,
        related_name='visibility_rules',
        verbose_name=_("Menu Item")
    )
    show_for = models.CharField(
        _("Show For"), max_length=20,
        choices=VISIBILITY_CHOICES, default='all'
    )
    role_name = models.CharField(
        _("Role Name"), max_length=100, blank=True,
        help_text=_("Specific role name if show_for='role'")
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Menu Visibility")
        verbose_name_plural = _("Menu Visibilities")
        ordering = ['menu_item', 'show_for']
        indexes = [
            models.Index(fields=['menu_item', 'show_for']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.menu_item.label} - {self.get_show_for_display()}"

    def check_visibility(self, user=None, role=None):
        """Check if item should be visible for given user/role."""
        if self.show_for == 'all':
            return True
        if self.show_for == 'logged_in':
            return user and user.is_authenticated
        if self.show_for == 'logged_out':
            return not (user and user.is_authenticated)
        if self.show_for == 'role':
            return role == self.role_name
        if self.show_for == 'staff':
            return user and user.is_staff
        if self.show_for == 'superuser':
            return user and user.is_superuser
        if self.show_for == 'vip':
            return user and getattr(user, 'is_vip', False)
        return False


# ─────────────────────────────────────────────
# LandingSection
# ─────────────────────────────────────────────

class LandingSection(TimeStampedModel):
    """
    Configurable landing page section.
    Supports drag-drop reordering and dynamic content JSON.
    """
    SECTION_TYPES = [
        ('hero', _('Hero Banner')),
        ('features', _('Features Grid')),
        ('testimonials', _('Testimonials')),
        ('cta', _('Call to Action')),
        ('stats', _('Statistics')),
        ('faq', _('FAQ Section')),
        ('team', _('Team Members')),
        ('pricing', _('Pricing Plans')),
        ('gallery', _('Image Gallery')),
        ('blog', _('Blog Posts')),
        ('video', _('Video Section')),
        ('map', _('Map Section')),
        ('newsletter', _('Newsletter Signup')),
        ('partners', _('Partners/Logos')),
        ('custom', _('Custom HTML')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Section Name"), max_length=200)
    section_type = models.CharField(
        _("Section Type"), max_length=30,
        choices=SECTION_TYPES, default='custom',
        db_index=True
    )
    content = models.JSONField(
        _("Content"), default=default_dict,
        help_text=_("Section content in JSON format")
    )
    sort_order = models.IntegerField(_("Sort Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    # Targeting
    page_slug = models.SlugField(
        _("Page Slug"), max_length=200, blank=True,
        help_text=_("Assign to a specific page by slug (blank = all)")
    )
    show_for = models.CharField(
        _("Show For"), max_length=20,
        choices=[
            ('all', _('All Users')),
            ('logged_in', _('Logged In')),
            ('logged_out', _('Logged Out')),
        ], default='all'
    )

    # Style
    background_color = models.CharField(
        _("Background Color"), max_length=20, blank=True
    )
    background_image = models.ImageField(
        _("Background Image"),
        upload_to='landing/sections/%Y/%m/',
        blank=True, null=True
    )
    css_class = models.CharField(_("CSS Class"), max_length=200, blank=True)
    custom_css = models.TextField(_("Custom CSS"), blank=True)

    # Stats
    view_count = models.PositiveIntegerField(_("View Count"), default=0)
    click_count = models.PositiveIntegerField(_("Click Count"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Landing Section")
        verbose_name_plural = _("Landing Sections")
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['section_type', 'is_active']),
            models.Index(fields=['sort_order', 'is_active']),
            models.Index(fields=['page_slug', 'is_active']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_section_type_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('landing_sections_all')
        cache.delete(f'landing_sections_{self.page_slug}')

    def reorder(self, new_order):
        """Update sort order."""
        self.sort_order = new_order
        LandingSection.objects.filter(id=self.id).update(sort_order=new_order)

    def get_content_field(self, key, default=None):
        """Safely get a content field."""
        return self.content.get(key, default)

    def set_content_field(self, key, value):
        """Set a content field and save."""
        self.content[key] = value
        LandingSection.objects.filter(id=self.id).update(content=self.content)

    def increment_view(self):
        LandingSection.objects.filter(id=self.id).update(view_count=F('view_count') + 1)

    def increment_click(self):
        LandingSection.objects.filter(id=self.id).update(click_count=F('click_count') + 1)

    @classmethod
    def get_for_page(cls, page_slug=''):
        """Get active sections for a page."""
        cache_key = f'landing_sections_{page_slug}'
        result = cache.get(cache_key)
        if result is None:
            q = Q(is_active=True) & (Q(page_slug=page_slug) | Q(page_slug=''))
            result = list(cls.objects.filter(q).order_by('sort_order'))
            cache.set(cache_key, result, 600)
        return result

    @classmethod
    def bulk_reorder(cls, order_data):
        """
        Bulk reorder sections.
        order_data: list of {id: int, sort_order: int}
        """
        with transaction.atomic():
            for item in order_data:
                cls.objects.filter(id=item['id']).update(sort_order=item['sort_order'])
        cache.delete('landing_sections_all')
