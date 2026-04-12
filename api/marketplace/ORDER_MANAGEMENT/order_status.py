"""
ORDER_MANAGEMENT/order_status.py — Order Status State Machine
"""
from api.marketplace.enums import OrderStatus
from api.marketplace.models import Order

VALID_TRANSITIONS = {
    OrderStatus.PENDING:          [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
    OrderStatus.CONFIRMED:        [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
    OrderStatus.PROCESSING:       [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED:          [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.RETURNED],
    OrderStatus.OUT_FOR_DELIVERY: [OrderStatus.DELIVERED, OrderStatus.RETURNED],
    OrderStatus.DELIVERED:        [OrderStatus.RETURNED],
    OrderStatus.CANCELLED:        [],
    OrderStatus.RETURNED:         [OrderStatus.REFUNDED],
    OrderStatus.REFUNDED:         [],
}

STATUS_DESCRIPTIONS = {
    OrderStatus.PENDING:          "Waiting for seller confirmation",
    OrderStatus.CONFIRMED:        "Seller has confirmed your order",
    OrderStatus.PROCESSING:       "Order is being prepared",
    OrderStatus.SHIPPED:          "Order has been shipped",
    OrderStatus.OUT_FOR_DELIVERY: "Out for delivery today",
    OrderStatus.DELIVERED:        "Successfully delivered",
    OrderStatus.CANCELLED:        "Order was cancelled",
    OrderStatus.RETURNED:         "Return initiated",
    OrderStatus.REFUNDED:         "Refund processed",
}

STATUS_COLORS = {
    OrderStatus.PENDING:          "yellow",
    OrderStatus.CONFIRMED:        "blue",
    OrderStatus.PROCESSING:       "blue",
    OrderStatus.SHIPPED:          "purple",
    OrderStatus.OUT_FOR_DELIVERY: "orange",
    OrderStatus.DELIVERED:        "green",
    OrderStatus.CANCELLED:        "red",
    OrderStatus.RETURNED:         "gray",
    OrderStatus.REFUNDED:         "teal",
}


def can_transition(current: str, new: str) -> bool:
    return new in VALID_TRANSITIONS.get(current, [])


def get_next_statuses(current: str) -> list:
    return VALID_TRANSITIONS.get(current, [])


def transition_order(order: Order, new_status: str, actor=None) -> dict:
    if not can_transition(order.status, new_status):
        return {
            "success": False,
            "error":   f"Cannot transition from '{order.status}' to '{new_status}'",
            "allowed": get_next_statuses(order.status),
        }
    old_status    = order.status
    order.status  = new_status
    order.save(update_fields=["status"])
    return {
        "success":     True,
        "from_status": old_status,
        "to_status":   new_status,
        "description": STATUS_DESCRIPTIONS.get(new_status, ""),
    }


def get_status_display(status: str) -> dict:
    return {
        "status":      status,
        "label":       status.replace("_"," ").title(),
        "description": STATUS_DESCRIPTIONS.get(status, ""),
        "color":       STATUS_COLORS.get(status, "gray"),
        "next":        get_next_statuses(status),
    }
