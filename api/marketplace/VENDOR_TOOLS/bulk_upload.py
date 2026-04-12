"""
VENDOR_TOOLS/bulk_upload.py — Production Bulk Upload (10,000+ products)
=========================================================================
Architecture:
  1. Vendor uploads CSV/Excel file via API (max 50MB)
  2. File is saved to storage → BulkUploadJob record created
  3. Celery task is dispatched immediately (HTTP response returns job_id)
  4. Celery processes rows in batches of 100 (no server timeout)
  5. Progress is tracked in Redis/cache (real-time polling)
  6. Errors are logged per-row (partial success allowed)
  7. Final report downloadable as CSV

CSV Schema (required columns):
  name, description, base_price, category_slug, stock
Optional:
  sale_price, color, size, sku, tags, weight_grams, short_description,
  meta_title, is_featured, condition

Excel (.xlsx) supported via openpyxl.

API flow:
  POST /api/marketplace/vendor/bulk-upload/
      → {"job_id": "uuid", "status": "queued", "rows_detected": 10000}

  GET  /api/marketplace/vendor/bulk-upload/{job_id}/status/
      → {"job_id": "uuid", "status": "processing",
          "progress": 45, "created": 4500, "errors": 23}

  GET  /api/marketplace/vendor/bulk-upload/{job_id}/errors/
      → CSV download of failed rows
"""
from __future__ import annotations

import csv
import io
import logging
import os
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

BATCH_SIZE            = 100     # rows per Celery sub-task
MAX_FILE_SIZE_MB      = 50
PROGRESS_CACHE_TTL    = 3600    # 1 hour
REQUIRED_COLUMNS      = {"name", "description", "base_price", "category_slug", "stock"}


# ─────────────────────────────────────────────────────────────────────────────
# Job tracking
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class UploadJobStatus:
    job_id: str
    status: str          # queued | processing | completed | failed
    total_rows: int      = 0
    processed_rows: int  = 0
    created: int         = 0
    updated: int         = 0
    skipped: int         = 0
    errors: int          = 0
    error_log: List[dict] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def progress_percent(self) -> int:
        if self.total_rows == 0:
            return 0
        return min(100, int(self.processed_rows / self.total_rows * 100))

    def to_dict(self) -> dict:
        return {
            "job_id":       self.job_id,
            "status":       self.status,
            "total_rows":   self.total_rows,
            "processed":    self.processed_rows,
            "progress":     self.progress_percent,
            "created":      self.created,
            "updated":      self.updated,
            "skipped":      self.skipped,
            "errors":       self.errors,
            "started_at":   self.started_at,
            "completed_at": self.completed_at,
        }


def _job_cache_key(job_id: str) -> str:
    return f"bulk_upload:job:{job_id}"


def get_job_status(job_id: str) -> Optional[dict]:
    """Polling endpoint — returns current job progress."""
    data = cache.get(_job_cache_key(job_id))
    return data


def _save_job_status(status: UploadJobStatus):
    cache.set(_job_cache_key(status.job_id), status.to_dict(), PROGRESS_CACHE_TTL)


# ─────────────────────────────────────────────────────────────────────────────
# File parser
# ─────────────────────────────────────────────────────────────────────────────

class BulkUploadParser:
    """Parses CSV or Excel into list of dicts. Validates required columns."""

    def parse(self, file_content: bytes, filename: str) -> List[dict]:
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".xlsx", ".xls"):
            return self._parse_excel(file_content)
        else:
            return self._parse_csv(file_content)

    def _parse_csv(self, content: bytes) -> List[dict]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        rows = [dict(row) for row in reader]
        self._validate_columns(set(rows[0].keys()) if rows else set())
        return rows

    def _parse_excel(self, content: bytes) -> List[dict]:
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl required: pip install openpyxl")

        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active

        rows = []
        headers = None
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(c).strip() if c else "" for c in row]
                self._validate_columns(set(headers))
                continue
            if all(c is None for c in row):
                continue  # skip empty rows
            row_dict = {headers[j]: (str(row[j]).strip() if row[j] is not None else "")
                        for j in range(len(headers))}
            rows.append(row_dict)
        wb.close()
        return rows

    def _validate_columns(self, columns: set):
        missing = REQUIRED_COLUMNS - {c.strip().lower() for c in columns}
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}. "
                f"Required: {REQUIRED_COLUMNS}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Row processor
# ─────────────────────────────────────────────────────────────────────────────

class RowProcessor:
    """
    Processes a single row from the upload file.
    Returns {"status": "created"|"updated"|"skipped"|"error", "detail": str}
    """

    def __init__(self, seller, tenant):
        self.seller = seller
        self.tenant = tenant
        self._category_cache = {}

    def process(self, row: dict, row_num: int) -> dict:
        try:
            return self._process_row(row, row_num)
        except Exception as e:
            logger.warning("[BulkUpload] Row %s error: %s | data: %s", row_num, e, row)
            return {"status": "error", "row": row_num, "detail": str(e)}

    @transaction.atomic
    def _process_row(self, row: dict, row_num: int) -> dict:
        from api.marketplace.models import Product, ProductVariant, ProductInventory, Category
        from api.marketplace.utils import unique_slugify, generate_sku

        # ── Validate & parse fields ───────────────────────────────────────────
        name = (row.get("name") or "").strip()
        if not name:
            return {"status": "skipped", "row": row_num, "detail": "Empty name"}

        description = (row.get("description") or "").strip()
        if not description:
            description = name

        try:
            base_price = Decimal(str(row.get("base_price", "0")).replace(",", ""))
        except InvalidOperation:
            return {"status": "error", "row": row_num, "detail": "Invalid base_price"}

        if base_price <= 0:
            return {"status": "error", "row": row_num, "detail": "base_price must be > 0"}

        sale_price_raw = str(row.get("sale_price") or "").strip()
        sale_price = None
        if sale_price_raw:
            try:
                sale_price = Decimal(sale_price_raw.replace(",", ""))
            except InvalidOperation:
                sale_price = None

        try:
            stock = int(str(row.get("stock", "0")).strip() or "0")
        except ValueError:
            stock = 0

        category_slug = (row.get("category_slug") or "").strip().lower()
        category = self._get_category(category_slug)

        # ── Create or update product ──────────────────────────────────────────
        sku = (row.get("sku") or "").strip()

        # Check by SKU first (for updates)
        existing_variant = None
        if sku:
            existing_variant = ProductVariant.objects.filter(sku=sku, tenant=self.tenant).first()

        if existing_variant:
            product = existing_variant.product
            # Update price
            product.base_price = base_price
            product.sale_price = sale_price
            product.save(update_fields=["base_price", "sale_price"])
            # Update stock
            ProductInventory.objects.filter(variant=existing_variant).update(quantity=stock)
            return {"status": "updated", "row": row_num, "detail": f"Updated SKU: {sku}"}

        # Create new product
        slug = unique_slugify(Product, name)
        product = Product.objects.create(
            tenant=self.tenant,
            seller=self.seller,
            category=category,
            name=name,
            slug=slug,
            description=description,
            short_description=(row.get("short_description") or "")[:500],
            base_price=base_price,
            sale_price=sale_price,
            tags=(row.get("tags") or ""),
            is_featured=str(row.get("is_featured", "")).lower() in ("true", "1", "yes"),
            meta_title=(row.get("meta_title") or "")[:255],
            status="draft",   # bulk uploads start as draft — seller reviews before publishing
        )

        # Create default variant
        auto_sku = sku or generate_sku(name)
        color    = (row.get("color") or "").strip()
        size     = (row.get("size") or "").strip()
        weight   = int(str(row.get("weight_grams") or "0").strip() or "0")

        variant = ProductVariant.objects.create(
            tenant=self.tenant,
            product=product,
            name=f"{color} {size}".strip() or "Default",
            sku=auto_sku,
            color=color,
            size=size,
            weight_grams=weight,
        )

        ProductInventory.objects.create(
            tenant=self.tenant,
            variant=variant,
            quantity=stock,
        )

        return {"status": "created", "row": row_num, "detail": f"Created: {name}"}

    def _get_category(self, slug: str):
        if slug in self._category_cache:
            return self._category_cache[slug]
        from api.marketplace.models import Category
        cat = Category.objects.filter(tenant=self.tenant, slug=slug).first()
        self._category_cache[slug] = cat
        return cat


# ─────────────────────────────────────────────────────────────────────────────
# Main upload handler (HTTP layer — starts Celery task)
# ─────────────────────────────────────────────────────────────────────────────

def handle_upload_request(file_content: bytes, filename: str, seller, tenant) -> dict:
    """
    Called from the API view.
    1. Validates file size
    2. Parses to detect row count
    3. Saves rows to cache
    4. Dispatches Celery task
    5. Returns job_id immediately (no timeout)
    """
    # Size check
    size_mb = len(file_content) / 1024 / 1024
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"File too large: {size_mb:.1f}MB. Max: {MAX_FILE_SIZE_MB}MB")

    parser = BulkUploadParser()
    rows = parser.parse(file_content, filename)

    if not rows:
        raise ValueError("File is empty or has no data rows.")

    job_id = str(uuid.uuid4())

    # Save raw rows to cache (chunked for memory efficiency)
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i: i + BATCH_SIZE]
        cache.set(
            f"bulk_upload:rows:{job_id}:{i}",
            batch,
            PROGRESS_CACHE_TTL,
        )

    # Store metadata
    job_meta = {
        "job_id":     job_id,
        "filename":   filename,
        "total_rows": len(rows),
        "seller_id":  seller.pk,
        "tenant_id":  tenant.pk,
        "batches":    list(range(0, len(rows), BATCH_SIZE)),
    }
    cache.set(f"bulk_upload:meta:{job_id}", job_meta, PROGRESS_CACHE_TTL)

    # Initial status
    status = UploadJobStatus(
        job_id=job_id,
        status="queued",
        total_rows=len(rows),
        started_at=timezone.now().isoformat(),
    )
    _save_job_status(status)

    # Dispatch Celery task
    try:
        from api.marketplace.tasks import process_bulk_upload
        process_bulk_upload.delay(job_id=job_id)
        logger.info(
            "[BulkUpload] Job %s queued | %s rows | seller#%s",
            job_id, len(rows), seller.pk,
        )
    except Exception as e:
        logger.error("[BulkUpload] Failed to dispatch Celery task: %s", e)
        # Fallback: process synchronously (not recommended for >1000 rows)
        _process_job_sync(job_id)

    return {
        "job_id":        job_id,
        "status":        "queued",
        "rows_detected": len(rows),
        "message":       f"{len(rows)} rows queued. Poll /status/ for progress.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Celery task body (called from tasks.py)
# ─────────────────────────────────────────────────────────────────────────────

def process_bulk_upload_job(job_id: str):
    """
    Celery task body. Processes all batches sequentially.
    This runs in a worker — no HTTP timeout.
    """
    from django.contrib.auth import get_user_model
    from api.marketplace.models import SellerProfile
    from api.tenants.models import Tenant

    meta = cache.get(f"bulk_upload:meta:{job_id}")
    if not meta:
        logger.error("[BulkUpload] Job %s: meta not found (expired?)", job_id)
        return

    # Load seller and tenant
    try:
        seller = SellerProfile.objects.get(pk=meta["seller_id"])
        tenant = Tenant.objects.get(pk=meta["tenant_id"])
    except Exception as e:
        logger.error("[BulkUpload] Job %s: seller/tenant not found: %s", job_id, e)
        return

    processor  = RowProcessor(seller=seller, tenant=tenant)
    job_status = UploadJobStatus(
        job_id=job_id,
        status="processing",
        total_rows=meta["total_rows"],
        started_at=timezone.now().isoformat(),
    )
    _save_job_status(job_status)

    # Process batch by batch
    for batch_offset in meta["batches"]:
        rows = cache.get(f"bulk_upload:rows:{job_id}:{batch_offset}")
        if not rows:
            logger.warning("[BulkUpload] Batch at offset %s missing for job %s", batch_offset, job_id)
            continue

        for i, row in enumerate(rows):
            row_num = batch_offset + i + 2  # +2 for header row
            result  = processor.process(row, row_num)

            job_status.processed_rows += 1
            if result["status"] == "created":
                job_status.created  += 1
            elif result["status"] == "updated":
                job_status.updated  += 1
            elif result["status"] == "skipped":
                job_status.skipped  += 1
            elif result["status"] == "error":
                job_status.errors   += 1
                if len(job_status.error_log) < 500:   # cap error log size
                    job_status.error_log.append(result)

        # Update progress after each batch
        _save_job_status(job_status)

        # Clean up batch from cache
        cache.delete(f"bulk_upload:rows:{job_id}:{batch_offset}")

    # Finalise
    job_status.status       = "completed"
    job_status.completed_at = timezone.now().isoformat()
    _save_job_status(job_status)

    logger.info(
        "[BulkUpload] Job %s complete | created=%s updated=%s skipped=%s errors=%s",
        job_id,
        job_status.created,
        job_status.updated,
        job_status.skipped,
        job_status.errors,
    )


def get_error_report_csv(job_id: str) -> str:
    """Generate CSV of failed rows for download."""
    data = cache.get(_job_cache_key(job_id))
    if not data:
        return "job_id,error\n" + f"{job_id},Job not found or expired\n"

    error_log = data.get("error_log", [])
    output    = io.StringIO()
    writer    = csv.DictWriter(output, fieldnames=["row", "status", "detail"])
    writer.writeheader()
    writer.writerows(error_log)
    return output.getvalue()


def _process_job_sync(job_id: str):
    """Fallback synchronous processing (development only)."""
    logger.warning("[BulkUpload] Processing synchronously — use Celery in production!")
    process_bulk_upload_job(job_id)
