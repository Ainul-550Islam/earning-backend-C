"""
VENDOR_TOOLS/product_export.py — Export Products to CSV/Excel
"""
import csv, io
from django.http import HttpResponse


def export_products_csv(seller, tenant) -> str:
    from api.marketplace.models import Product
    products = Product.objects.filter(
        seller=seller, tenant=tenant
    ).prefetch_related("attributes","variants__inventory").select_related("category")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "name","slug","description","short_description","category",
        "base_price","sale_price","status","condition","is_featured",
        "tags","sku","color","size","stock","weight_grams",
        "average_rating","review_count","total_sales",
    ])
    for p in products:
        for v in p.variants.all():
            try:
                stock = v.inventory.quantity
            except Exception:
                stock = 0
            writer.writerow([
                p.name, p.slug, p.description[:200], p.short_description,
                p.category.name if p.category else "",
                p.base_price, p.sale_price or "",
                p.status, p.condition, p.is_featured,
                p.tags, v.sku, v.color, v.size, stock, v.weight_grams,
                p.average_rating, p.review_count, p.total_sales,
            ])
    return output.getvalue()


def export_products_xlsx(seller, tenant) -> bytes:
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl required: pip install openpyxl")

    from api.marketplace.models import Product
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products"

    headers = ["Name","Category","Base Price","Sale Price","SKU","Stock","Status","Rating","Sales"]
    ws.append(headers)

    products = Product.objects.filter(seller=seller, tenant=tenant).select_related("category")
    for p in products:
        for v in p.variants.all():
            try:
                stock = v.inventory.quantity
            except Exception:
                stock = 0
            ws.append([
                p.name, p.category.name if p.category else "", float(p.base_price),
                float(p.sale_price) if p.sale_price else "", v.sku, stock,
                p.status, float(p.average_rating), p.total_sales,
            ])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_orders_csv(seller, tenant, from_date=None, to_date=None) -> str:
    from api.marketplace.models import OrderItem
    qs = OrderItem.objects.filter(seller=seller, tenant=tenant).select_related("order","variant__product")
    if from_date:
        qs = qs.filter(created_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__date__lte=to_date)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order Number","Date","Product","SKU","Qty","Unit Price","Subtotal","Commission","Seller Net","Status"])
    for item in qs.order_by("-created_at")[:5000]:
        writer.writerow([
            item.order.order_number,
            item.created_at.strftime("%Y-%m-%d"),
            item.product_name, item.sku,
            item.quantity, item.unit_price, item.subtotal,
            item.commission_amount, item.seller_net,
            item.item_status,
        ])
    return output.getvalue()
