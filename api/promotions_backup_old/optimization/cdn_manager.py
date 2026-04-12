# =============================================================================
# api/promotions/optimization/cdn_manager.py
# CDN Manager — Cloudflare / AWS CloudFront / BunnyCDN integration
# Static assets ও proof screenshots CDN এ serve করে
# =============================================================================

import hashlib
import hmac
import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse, quote

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('optimization.cdn')

# settings.py তে define করুন:
# CDN_PROVIDER          = 'cloudflare'  # cloudflare | cloudfront | bunnycdn | none
# CDN_BASE_URL          = 'https://cdn.yoursite.com'
# CDN_CLOUDFRONT_KEY_ID = 'APKAXXXXXX'
# CDN_CLOUDFRONT_PRIVATE_KEY = '-----BEGIN RSA PRIVATE KEY-----...'
# CDN_BUNNYCDN_API_KEY  = 'xxxx'
# CDN_BUNNYCDN_ZONE     = 'yourzone'
# CDN_SIGNED_URL_EXPIRE = 3600  # seconds

CDN_PROVIDER         = getattr(settings, 'CDN_PROVIDER', 'none')
CDN_BASE_URL         = getattr(settings, 'CDN_BASE_URL', '')
CDN_SIGNED_URL_TTL   = getattr(settings, 'CDN_SIGNED_URL_EXPIRE', 3600)
CACHE_PREFIX_CDN     = 'opt:cdn:{}'


# =============================================================================
# ── CDN URL BUILDER ──────────────────────────────────────────────────────────
# =============================================================================

class CDNManager:
    """
    Multi-provider CDN URL management।

    Providers:
    - Cloudflare CDN (free tier available)
    - AWS CloudFront (signed URLs for private content)
    - BunnyCDN (affordable, fast)
    - None (direct S3/storage URL — no CDN)

    Features:
    - Public URL generation
    - Signed URL (private content — proof screenshots)
    - Image transformation URL (resize, crop on-the-fly)
    - Cache invalidation
    - Bandwidth tracking
    """

    def __init__(self, provider: str = None):
        self.provider = provider or CDN_PROVIDER

    def get_url(self, path: str, signed: bool = False, ttl: int = None) -> str:
        """
        CDN URL তৈরি করে।

        Args:
            path:   Storage path (e.g., 'proofs/2024/01/screenshot.webp')
            signed: Private content এর জন্য signed URL
            ttl:    Signed URL expiry (seconds)
        """
        if not CDN_BASE_URL or self.provider == 'none':
            return self._direct_storage_url(path)

        if signed:
            return self._signed_url(path, ttl or CDN_SIGNED_URL_TTL)

        return self._public_url(path)

    def get_image_url(
        self,
        path:    str,
        width:   int  = None,
        height:  int  = None,
        quality: int  = 80,
        format:  str  = 'webp',
        signed:  bool = False,
    ) -> str:
        """
        Image transformation URL তৈরি করে।
        Cloudflare Images / CloudFront Lambda@Edge এর জন্য।

        Args:
            width, height: Resize dimensions
            quality:       Image quality (0-100)
            format:        Output format (webp, jpeg, avif)
        """
        base_url = self.get_url(path, signed=signed)

        if self.provider == 'cloudflare':
            return self._cloudflare_image_url(base_url, width, height, quality, format)
        elif self.provider == 'cloudfront':
            return self._cloudfront_image_url(base_url, width, height, quality, format)
        elif self.provider == 'imgix':
            return self._imgix_url(base_url, width, height, quality, format)

        # No image transformation — just return the base URL
        return base_url

    def invalidate_cache(self, paths: list[str]) -> dict:
        """CDN cache invalidate করে।"""
        if self.provider == 'cloudflare':
            return self._cloudflare_invalidate(paths)
        elif self.provider == 'cloudfront':
            return self._cloudfront_invalidate(paths)
        elif self.provider == 'bunnycdn':
            return self._bunnycdn_invalidate(paths)
        logger.info(f'CDN invalidation skipped (provider={self.provider}): {paths}')
        return {'status': 'skipped', 'paths': paths}

    def get_proof_url(self, submission_id: int, filename: str) -> str:
        """
        Proof screenshot এর signed URL তৈরি করে।
        শুধু authorized user দেখতে পারবে।
        """
        path = f'proofs/{submission_id}/{filename}'
        url  = self.get_url(path, signed=True, ttl=3600)

        # Cache করো (same URL বারবার generate না করা)
        cache_key = CACHE_PREFIX_CDN.format(hashlib.md5(path.encode()).hexdigest())
        cache.set(cache_key, url, timeout=CDN_SIGNED_URL_TTL - 60)  # 1 min buffer

        return url

    # ── Provider Implementations ──────────────────────────────────────────────

    def _public_url(self, path: str) -> str:
        """Public CDN URL।"""
        clean_path = path.lstrip('/')
        return f'{CDN_BASE_URL.rstrip("/")}/{clean_path}'

    def _signed_url(self, path: str, ttl: int) -> str:
        """Signed URL — provider অনুযায়ী।"""
        if self.provider == 'cloudfront':
            return self._cloudfront_signed_url(path, ttl)
        elif self.provider == 'bunnycdn':
            return self._bunnycdn_signed_url(path, ttl)
        elif self.provider == 'cloudflare':
            return self._cloudflare_signed_url(path, ttl)
        return self._public_url(path)

    # ── Cloudflare ────────────────────────────────────────────────────────────

    def _cloudflare_image_url(
        self, base_url: str, width: int, height: int, quality: int, fmt: str
    ) -> str:
        """Cloudflare Image Resizing URL format।"""
        # https://developers.cloudflare.com/images/image-resizing/url-format/
        options = []
        if width:   options.append(f'w={width}')
        if height:  options.append(f'h={height}')
        if quality: options.append(f'q={quality}')
        if fmt:     options.append(f'f={fmt}')

        if not options:
            return base_url

        parsed   = urlparse(base_url)
        cdn_path = f'/cdn-cgi/image/{",".join(options)}{parsed.path}'
        return f'{parsed.scheme}://{parsed.netloc}{cdn_path}'

    def _cloudflare_signed_url(self, path: str, ttl: int) -> str:
        """Cloudflare Signed URL (Cloudflare Workers + signed URLs)।"""
        secret = getattr(settings, 'CDN_CLOUDFLARE_SIGNING_KEY', '')
        if not secret:
            return self._public_url(path)

        expiry    = int(time.time()) + ttl
        to_sign   = f'{path}{expiry}'
        signature = hmac.new(
            secret.encode(), to_sign.encode(), hashlib.sha256
        ).hexdigest()[:20]

        base = self._public_url(path)
        return f'{base}?exp={expiry}&sig={signature}'

    def _cloudflare_invalidate(self, paths: list[str]) -> dict:
        """Cloudflare cache purge।"""
        api_token = getattr(settings, 'CDN_CLOUDFLARE_API_TOKEN', '')
        zone_id   = getattr(settings, 'CDN_CLOUDFLARE_ZONE_ID', '')
        if not api_token or not zone_id:
            return {'status': 'not_configured'}

        try:
            import requests
            urls = [self._public_url(p) for p in paths]
            resp = requests.post(
                f'https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache',
                headers={'Authorization': f'Bearer {api_token}'},
                json={'files': urls},
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f'Cloudflare cache purged: {len(paths)} URLs')
            return {'status': 'success', 'cf_response': result}
        except Exception as e:
            logger.error(f'Cloudflare invalidation failed: {e}')
            return {'status': 'error', 'error': str(e)}

    # ── AWS CloudFront ────────────────────────────────────────────────────────

    def _cloudfront_signed_url(self, path: str, ttl: int) -> str:
        """CloudFront signed URL — RSA private key দিয়ে sign করে।"""
        key_id      = getattr(settings, 'CDN_CLOUDFRONT_KEY_ID', '')
        private_key = getattr(settings, 'CDN_CLOUDFRONT_PRIVATE_KEY', '')
        if not key_id or not private_key:
            return self._public_url(path)

        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            import json, base64

            expiry   = int(time.time()) + ttl
            url      = self._public_url(path)
            policy   = json.dumps({
                'Statement': [{
                    'Resource': url,
                    'Condition': {'DateLessThan': {'AWS:EpochTime': expiry}},
                }]
            }, separators=(',', ':'))

            private_key_obj = serialization.load_pem_private_key(
                private_key.encode() if isinstance(private_key, str) else private_key,
                password=None,
            )
            signature = private_key_obj.sign(policy.encode(), padding.PKCS1v15(), hashes.SHA1())
            sig_b64   = base64.b64encode(signature).decode().replace('+', '-').replace('=', '_').replace('/', '~')
            policy_b64 = base64.b64encode(policy.encode()).decode().replace('+', '-').replace('=', '_').replace('/', '~')

            return f'{url}?Policy={policy_b64}&Signature={sig_b64}&Key-Pair-Id={key_id}'

        except Exception as e:
            logger.error(f'CloudFront signed URL failed: {e}')
            return self._public_url(path)

    def _cloudfront_image_url(
        self, base_url: str, width: int, height: int, quality: int, fmt: str
    ) -> str:
        """CloudFront + Lambda@Edge image resize।"""
        params = []
        if width:   params.append(f'w={width}')
        if height:  params.append(f'h={height}')
        if quality: params.append(f'q={quality}')
        if fmt:     params.append(f'f={fmt}')
        if params:
            sep = '&' if '?' in base_url else '?'
            return f'{base_url}{sep}{"&".join(params)}'
        return base_url

    def _cloudfront_invalidate(self, paths: list[str]) -> dict:
        """CloudFront invalidation।"""
        try:
            import boto3
            distribution_id = getattr(settings, 'CDN_CLOUDFRONT_DISTRIBUTION_ID', '')
            if not distribution_id:
                return {'status': 'not_configured'}

            cf = boto3.client('cloudfront')
            cf.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    'Paths': {'Quantity': len(paths), 'Items': [f'/{p.lstrip("/")}' for p in paths]},
                    'CallerReference': str(int(time.time())),
                },
            )
            logger.info(f'CloudFront invalidation created: {len(paths)} paths')
            return {'status': 'success'}
        except Exception as e:
            logger.error(f'CloudFront invalidation failed: {e}')
            return {'status': 'error', 'error': str(e)}

    # ── BunnyCDN ──────────────────────────────────────────────────────────────

    def _bunnycdn_signed_url(self, path: str, ttl: int) -> str:
        """BunnyCDN Token Authentication URL।"""
        security_key = getattr(settings, 'CDN_BUNNYCDN_SECURITY_KEY', '')
        if not security_key:
            return self._public_url(path)

        expiry       = int(time.time()) + ttl
        clean_path   = '/' + path.lstrip('/')
        to_hash      = security_key + clean_path + str(expiry)
        token        = hashlib.md5(to_hash.encode()).digest()
        token_b64    = (
            __import__('base64').b64encode(token).decode()
            .replace('+', '-').replace('/', '_').replace('=', '')
        )
        base_url     = self._public_url(path)
        return f'{base_url}?token={token_b64}&expires={expiry}'

    def _bunnycdn_invalidate(self, paths: list[str]) -> dict:
        """BunnyCDN cache purge।"""
        api_key  = getattr(settings, 'CDN_BUNNYCDN_API_KEY', '')
        zone     = getattr(settings, 'CDN_BUNNYCDN_ZONE', '')
        if not api_key:
            return {'status': 'not_configured'}

        try:
            import requests
            results = []
            for path in paths:
                url  = self._public_url(path)
                resp = requests.get(
                    f'https://api.bunny.net/purge?url={quote(url, safe="")}',
                    headers={'AccessKey': api_key},
                    timeout=5,
                )
                results.append({'path': path, 'status': resp.status_code})
            return {'status': 'success', 'results': results}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    # ── Imgix ─────────────────────────────────────────────────────────────────

    def _imgix_url(
        self, base_url: str, width: int, height: int, quality: int, fmt: str
    ) -> str:
        """Imgix image transformation URL।"""
        params = {}
        if width:   params['w'] = width
        if height:  params['h'] = height
        if quality: params['q'] = quality
        if fmt:     params['fm'] = fmt
        params['auto'] = 'format,compress'

        param_str = '&'.join(f'{k}={v}' for k, v in params.items())
        sep       = '&' if '?' in base_url else '?'
        return f'{base_url}{sep}{param_str}'

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _direct_storage_url(path: str) -> str:
        """CDN না থাকলে direct storage URL।"""
        from django.core.files.storage import default_storage
        try:
            return default_storage.url(path)
        except Exception:
            return path


# ── Singleton ──────────────────────────────────────────────────────────────────
cdn = CDNManager()
