import django_filters as filters
from .choices import CodeStatus, DeliveryMethod, InventoryStatus, ItemStatus, ItemType
from .models import RedemptionCode, RewardItem, UserInventory


class RewardItemFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=ItemStatus.choices)
    item_type = filters.MultipleChoiceFilter(choices=ItemType.choices)
    min_points = filters.NumberFilter(field_name="points_cost", lookup_expr="gte")
    max_points = filters.NumberFilter(field_name="points_cost", lookup_expr="lte")
    in_stock = filters.BooleanFilter(method="filter_in_stock")
    is_featured = filters.BooleanFilter()
    search = filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = RewardItem
        fields = ["status", "item_type", "is_featured"]

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.in_stock()
        return queryset.out_of_stock()

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class UserInventoryFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=InventoryStatus.choices)
    item = filters.UUIDFilter(field_name="item__id")
    delivery_method = filters.ChoiceFilter(choices=DeliveryMethod.choices)
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = UserInventory
        fields = ["status", "delivery_method"]


class RedemptionCodeFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=CodeStatus.choices)
    batch_id = filters.CharFilter(lookup_expr="iexact")
    item = filters.UUIDFilter(field_name="item__id")

    class Meta:
        model = RedemptionCode
        fields = ["status", "batch_id", "item"]
