"""order_invoice.py — Invoice generation"""
from api.marketplace.models import Order


def generate_invoice_data(order: Order) -> dict:
    return {
        "invoice_number": f"INV-{order.order_number}",
        "order_number": order.order_number,
        "date": order.created_at.strftime("%Y-%m-%d"),
        "customer": order.shipping_name,
        "address": order.shipping_address,
        "city": order.shipping_city,
        "items": [
            {
                "name": item.product_name,
                "variant": item.variant_name,
                "qty": item.quantity,
                "unit_price": str(item.unit_price),
                "subtotal": str(item.subtotal),
            }
            for item in order.items.all()
        ],
        "subtotal": str(order.subtotal),
        "discount": str(order.discount_amount),
        "shipping": str(order.shipping_charge),
        "tax": str(order.tax_amount),
        "total": str(order.total_price),
        "payment_method": order.payment_method,
    }
