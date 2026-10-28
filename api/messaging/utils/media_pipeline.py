"""
Media Upload Pipeline — S3/Cloud storage + image compression + video transcoding.
World-class media handling like WhatsApp, Telegram, Discord.

Features:
- Direct S3 presigned upload (client uploads directly, no server bottleneck)
- Auto image compression (JPEG progressive, WebP conversion)
- Video thumbnail generation
- Virus scanning (ClamAV or VirusTotal)
- NSFW detection (Google Vision API)
- CDN URL generation
"""
from __future__ import annotations
import logging
import uuid
import os
import tempfile  # noqa: F401  (module-level so tests can patch it)
import time  # noqa: F401  (module-level so tests can patch it)
import subprocess  # noqa: F401  (module-level so tests can patch it)
import io  # noqa: F401  (module-level so tests can patch it)
from typing import Any, Optional
import requests  # noqa: F401  (module-level so tests can patch it)
import boto3  # noqa: F401  (module-level so tests can patch it)

logger = logging.getLogger(__name__)

# Google Vision SafeSearch returns categorical likelihood levels, not a raw
# numeric score - this maps them to a 0-1 scale for MediaAttachment.nsfw_score.
_SAFE_SEARCH_SCORE = {
    "VERY_UNLIKELY": 0.0,
    "UNLIKELY": 0.2,
    "POSSIBLE": 0.5,
    "LIKELY": 0.8,
    "VERY_LIKELY": 1.0,
    "UNKNOWN": 0.0,
}


def generate_presigned_upload_url(
    *,
    user_id: Any,
    filename: str,
    mimetype: str,
    file_size: int,
    chat_id: Optional[str] = None,
) -> dict:
    """
    Generate a presigned S3 URL for direct client upload.
    Returns {upload_url, file_key, cdn_url, expires_in}.
    Client uploads directly to S3 — no server bandwidth used.
    """
    from django.conf import settings
    from botocore.exceptions import ClientError

    _validate_upload(filename, mimetype, file_size)

    s3_bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    s3_region = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
    cdn_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)

    if not s3_bucket:
        # Local fallback for dev
        return _local_upload_fallback(user_id, filename, mimetype)

    file_key = _build_file_key(user_id, filename, chat_id)
    s3 = boto3.client("s3", region_name=s3_region)

    try:
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": s3_bucket,
                "Key": file_key,
                "ContentType": mimetype,
                "ContentLength": file_size,
                "Metadata": {
                    "user_id": str(user_id),
                    "original_filename": filename[:255],
                },
            },
            ExpiresIn=900,  # 15 minutes to upload
        )
        cdn_url = f"https://{cdn_domain}/{file_key}" if cdn_domain else f"https://{s3_bucket}.s3.amazonaws.com/{file_key}"

        return {
            "upload_url": upload_url,
            "file_key": file_key,
            "cdn_url": cdn_url,
            "expires_in": 900,
            "method": "PUT",
            "headers": {"Content-Type": mimetype},
        }
    except ClientError as exc:
        logger.error("generate_presigned_upload_url: %s", exc)
        raise


def _validate_upload(filename: str, mimetype: str, file_size: int) -> None:
    from ..constants import (
        MAX_ATTACHMENT_SIZE_BYTES, MAX_AUDIO_SIZE_BYTES,
        MAX_VIDEO_SIZE_BYTES, ALLOWED_ATTACHMENT_MIMETYPES,
    )
    from ..exceptions import MediaTooLargeError, MediaTypeNotAllowedError
    if mimetype not in ALLOWED_ATTACHMENT_MIMETYPES:
        raise MediaTypeNotAllowedError(f"Mimetype '{mimetype}' is not allowed.")
    if mimetype.startswith("video/"):
        if file_size > MAX_VIDEO_SIZE_BYTES:
            raise MediaTooLargeError(f"Video exceeds {MAX_VIDEO_SIZE_BYTES // 1_000_000}MB limit.")
    elif mimetype.startswith("audio/"):
        if file_size > MAX_AUDIO_SIZE_BYTES:
            raise MediaTooLargeError(f"Audio exceeds {MAX_AUDIO_SIZE_BYTES // 1_000_000}MB limit.")
    elif file_size > MAX_ATTACHMENT_SIZE_BYTES:
        raise MediaTooLargeError(f"File exceeds {MAX_ATTACHMENT_SIZE_BYTES // 1_000_000}MB limit.")


def _build_file_key(user_id: Any, filename: str, chat_id: Optional[str]) -> str:
    """Build a structured S3 key."""
    from django.utils import timezone
    ext = os.path.splitext(filename)[1].lower()[:10]
    date = timezone.now().strftime("%Y/%m/%d")
    unique = uuid.uuid4().hex[:12]
    if chat_id and _is_valid_uuid(chat_id):
        return f"messaging/chats/{chat_id}/{date}/{unique}{ext}"
    return f"messaging/users/{user_id}/{date}/{unique}{ext}"


def _is_valid_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _local_upload_fallback(user_id: Any, filename: str, mimetype: str) -> dict:
    """Dev fallback — returns a mock response."""
    logger.warning("_local_upload_fallback: AWS not configured, using mock.")
    fake_key = f"dev/{uuid.uuid4().hex}/{filename}"
    return {
        "upload_url": f"/dev/upload/{fake_key}",
        "file_key": fake_key,
        "cdn_url": f"http://localhost:8000/media/{fake_key}",
        "expires_in": 900,
        "method": "PUT",
        "headers": {"Content-Type": mimetype},
    }


def process_image_after_upload(file_key: str, mimetype: str) -> dict:
    """
    Post-upload processing pipeline for images.
    1. Download from S3
    2. Compress + convert to WebP
    3. Generate thumbnail (320x320)
    4. Re-upload processed versions
    5. Return CDN URLs
    Called by Celery task after upload confirmation.
    """
    from django.conf import settings

    results = {"original": file_key, "compressed": None, "thumbnail": None, "webp": None}

    try:
        s3_bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
        cdn_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)

        if not s3_bucket:
            return results

        from PIL import Image

        s3 = boto3.client("s3", region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"))

        # Download
        obj = s3.get_object(Bucket=s3_bucket, Key=file_key)
        img_data = obj["Body"].read()
        img = Image.open(io.BytesIO(img_data))

        # Strip EXIF for privacy
        img_no_exif = _strip_exif(img)

        # Convert to RGB if needed
        if img_no_exif.mode not in ("RGB", "RGBA"):
            img_no_exif = img_no_exif.convert("RGB")

        # Generate thumbnail
        thumb = img_no_exif.copy()
        thumb.thumbnail((320, 320), Image.LANCZOS)
        thumb_key = file_key.replace(".", "_thumb.")
        thumb_buf = io.BytesIO()
        thumb.save(thumb_buf, format="JPEG", quality=70, optimize=True, progressive=True)
        thumb_buf.seek(0)
        s3.put_object(Bucket=s3_bucket, Key=thumb_key, Body=thumb_buf, ContentType="image/jpeg")
        results["thumbnail"] = f"https://{cdn_domain}/{thumb_key}" if cdn_domain else thumb_key

        # Generate WebP version
        webp_key = os.path.splitext(file_key)[0] + ".webp"
        webp_buf = io.BytesIO()
        img_no_exif.save(webp_buf, format="WEBP", quality=80, method=6)
        webp_buf.seek(0)
        s3.put_object(Bucket=s3_bucket, Key=webp_key, Body=webp_buf, ContentType="image/webp")
        results["webp"] = f"https://{cdn_domain}/{webp_key}" if cdn_domain else webp_key

        # Compressed JPEG
        compressed_key = os.path.splitext(file_key)[0] + "_compressed.jpg"
        comp_buf = io.BytesIO()
        max_size = (1920, 1920)
        if img_no_exif.size[0] > max_size[0] or img_no_exif.size[1] > max_size[1]:
            img_no_exif.thumbnail(max_size, Image.LANCZOS)
        img_no_exif.save(comp_buf, format="JPEG", quality=85, optimize=True, progressive=True)
        comp_buf.seek(0)
        s3.put_object(Bucket=s3_bucket, Key=compressed_key, Body=comp_buf, ContentType="image/jpeg")
        results["compressed"] = f"https://{cdn_domain}/{compressed_key}" if cdn_domain else compressed_key

        logger.info("process_image_after_upload: %s → thumb=%s webp=%s", file_key, thumb_key, webp_key)

    except ImportError:
        logger.warning("process_image_after_upload: Pillow not installed.")
    except Exception as exc:
        logger.error("process_image_after_upload: %s → %s", file_key, exc)

    return results


def _strip_exif(img: "Image.Image") -> "Image.Image":
    """Remove EXIF metadata for privacy (GPS location, device info, etc.)."""
    try:
        from PIL import Image
        # Image.getdata() was deprecated in Pillow 10.2.0 (removal version
        # 14.0, ~2027-10-15) in favour of get_flattened_data(). Use the new
        # method when available; fall back for hosts pinned to older Pillow.
        if hasattr(img, "get_flattened_data"):
            data = img.get_flattened_data()
        else:
            data = list(img.getdata())
        clean = Image.new(img.mode, img.size)
        clean.putdata(data)
        return clean
    except Exception as exc:
        # Falling back to the original image means any EXIF data (GPS
        # coordinates, device info) ships as-is - previously silent with
        # no log line at all, so a failure here was invisible in
        # production. Not blocking the upload on this failure is still the
        # right default (matches this module's fail-open stance elsewhere,
        # e.g. scan_file_for_viruses), but it should at least be visible.
        logger.warning("_strip_exif: failed, returning image with EXIF intact: %s", exc)
        return img


def generate_video_thumbnail(file_key: str) -> Optional[str]:
    """Extract first frame of video as thumbnail."""
    from django.conf import settings

    tmp_path = None
    thumb_path = None
    try:

        s3_bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
        cdn_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
        if not s3_bucket:
            return None

        s3 = boto3.client("s3")
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_vid:
            tmp_path = tmp_vid.name
            s3.download_fileobj(s3_bucket, file_key, tmp_vid)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_thumb:
            thumb_path = tmp_thumb.name

        # FFmpeg extract frame at 1s
        subprocess.run([
            "ffmpeg", "-i", tmp_path,
            "-ss", "00:00:01.000",
            "-vframes", "1",
            "-vf", "scale=320:320:force_original_aspect_ratio=decrease",
            "-q:v", "3",
            thumb_path,
        ], check=True, capture_output=True, timeout=30)

        thumb_key = os.path.splitext(file_key)[0] + "_thumb.jpg"
        with open(thumb_path, "rb") as f:
            s3.put_object(Bucket=s3_bucket, Key=thumb_key, Body=f, ContentType="image/jpeg")

        cdn_url = f"https://{cdn_domain}/{thumb_key}" if cdn_domain else thumb_key
        return cdn_url
    except FileNotFoundError:
        logger.warning("generate_video_thumbnail: ffmpeg not installed.")
        return None
    except Exception as exc:
        logger.error("generate_video_thumbnail: %s → %s", file_key, exc)
        return None
    finally:
        # Part 6 audit fix: this used to unlink both temp files only on the
        # success path. Any failure above (corrupt upload, unsupported
        # codec, the 30s ffmpeg timeout, an S3 error) skipped straight to
        # an except block that returned early, leaking the downloaded
        # video - often multiple MB - and any partial thumbnail on disk
        # forever. Video processing failures are common enough on
        # user-submitted content that this would slowly exhaust disk on
        # whatever worker runs this Celery task. Cleanup now always runs.
        for p in (tmp_path, thumb_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError as exc:
                    logger.warning("generate_video_thumbnail: cleanup failed for %s: %s", p, exc)


def scan_file_for_viruses(file_key: str) -> bool:
    """
    Scan uploaded file for viruses using ClamAV or VirusTotal API.
    Returns True if clean, False if infected.
    """
    from django.conf import settings

    virustotal_key = getattr(settings, "VIRUSTOTAL_API_KEY", None)
    if not virustotal_key:
        logger.debug("scan_file_for_viruses: VirusTotal not configured, skipping scan.")
        return True

    try:
        from django.conf import settings

        s3_bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME")
        cdn_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "")
        url = f"https://{cdn_domain}/{file_key}" if cdn_domain else f"https://s3.amazonaws.com/{s3_bucket}/{file_key}"

        resp = requests.post(
            "https://www.virustotal.com/api/v3/urls",
            headers={"x-apikey": virustotal_key},
            data={"url": url},
            timeout=10,
        )
        resp.raise_for_status()
        analysis_id = resp.json()["data"]["id"]

        for _ in range(6):
            time.sleep(5)
            report = requests.get(
                f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                headers={"x-apikey": virustotal_key},
                timeout=10,
            )
            stats = report.json().get("data", {}).get("attributes", {}).get("stats", {})
            if report.json().get("data", {}).get("attributes", {}).get("status") == "completed":
                malicious = stats.get("malicious", 0)
                if malicious > 0:
                    logger.warning("scan_file_for_viruses: INFECTED file_key=%s malicious=%d", file_key, malicious)
                    return False
                return True
        return True
    except Exception as exc:
        logger.error("scan_file_for_viruses: %s → %s", file_key, exc)
        return True  # Allow on error to not block


def detect_nsfw(image_url: str) -> dict:
    """
    Detect NSFW/explicit content using Google Vision API SafeSearch.
    Returns {is_nsfw, toxic_score, is_safe, adult, violence, medical, racy}.

    Part 6 audit bug fix: this used to return only {is_safe, adult,
    violence, medical, racy}. Its only caller, tasks.process_image_task
    (already audited/fixed in a prior session), reads
    nsfw_result.get("is_nsfw") and nsfw_result.get("toxic_score", 0.0) to
    decide MediaAttachment.status/is_nsfw/nsfw_score - neither key existed
    here, so .get() silently returned the falsy default every time. NSFW
    moderation for images was a complete no-op: every uploaded image was
    stored as is_nsfw=False, nsfw_score=0.0, status=READY, regardless of
    what Vision actually detected. MediaAttachment's own is_nsfw/
    nsfw_score model fields (models.py) confirm this is the shape the rest
    of the system expects, so this function was the side that needed to
    change, not the already-audited task. toxic_score is derived from
    Vision's categorical likelihood levels (there is no raw numeric score
    in the SafeSearch API) via the same LIKELY/VERY_LIKELY threshold
    already used for is_safe, so behavior for existing is_safe-only
    callers is unchanged.
    """
    from django.conf import settings

    google_key = getattr(settings, "GOOGLE_VISION_API_KEY", None)
    if not google_key:
        return {"is_nsfw": False, "toxic_score": 0.0, "is_safe": True}

    try:
        payload = {
            "requests": [{
                "image": {"source": {"imageUri": image_url}},
                "features": [{"type": "SAFE_SEARCH_DETECTION"}],
            }]
        }
        resp = requests.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={google_key}",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        annotations = resp.json().get("responses", [{}])[0].get("safeSearchAnnotation", {})
        dangerous = {"LIKELY", "VERY_LIKELY"}
        adult     = annotations.get("adult", "UNKNOWN")
        violence  = annotations.get("violence", "UNKNOWN")
        is_safe   = adult not in dangerous and violence not in dangerous
        toxic_score = max(
            _SAFE_SEARCH_SCORE.get(adult, 0.0),
            _SAFE_SEARCH_SCORE.get(violence, 0.0),
        )
        return {
            "is_nsfw": not is_safe,
            "toxic_score": toxic_score,
            "is_safe": is_safe,
            "adult": adult,
            "violence": violence,
            "medical": annotations.get("medical", "UNKNOWN"),
            "racy": annotations.get("racy", "UNKNOWN"),
        }
    except Exception as exc:
        logger.error("detect_nsfw: %s → %s", image_url, exc)
        return {"is_nsfw": False, "toxic_score": 0.0, "is_safe": True}