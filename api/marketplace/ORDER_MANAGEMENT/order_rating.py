"""ORDER_MANAGEMENT/order_rating.py — Rate delivered orders"""
from api.marketplace.models import Order, OrderItem, ProductReview
from api.marketplace.enums import OrderStatus


def can_rate_order(order: Order) -> bool:
    return order.status == OrderStatus.DELIVERED


def rate_order_items(order: Order, user, ratings: list) -> list:
    """
    ratings = [{"order_item_id": 1, "rating": 5, "title": "Great!", "body": "..."}]
    """
    created = []
    for r in ratings:
        try:
            item = OrderItem.objects.get(pk=r["order_item_id"], order=order)
            if item.is_reviewed:
                continue
            review = ProductReview.objects.create(
                tenant=order.tenant,
                product=item.variant.product if item.variant else None,
                order_item=item,
                user=user,
                rating=r.get("rating", 5),
                title=r.get("title", ""),
                body=r.get("body", ""),
                is_verified_purchase=True,
            )
            item.is_reviewed = True
            item.save(update_fields=["is_reviewed"])
            created.append(review)
        except Exception:
            continue
    return created
