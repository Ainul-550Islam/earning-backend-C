"""
SmartLink — Integration Base Class
=====================================
Before this file, 7 integration files each duplicated the same HTTP request
pattern with no retry, no consistent timeout, and no structured logging:

    resp = requests.post(url, json=payload, headers=headers)

Now they extend IntegrationBase and call self._post(url, payload).

Fixed integration files (previously marked ⚠️):
  TikTokEventsAPI.py              — no retry
  TwitterAdsConversionAPI.py      — no retry
  FacebookPixelService.py         — no retry
  GoogleAdsService.py             — no retry, no timeout
  GA4MeasurementProtocol.py       — no retry
  SnapchatConversionsAPI.py        — no retry
  PushNotificationRouter.py       — no try/except, no retry, no timeout, no logging
"""
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger('smartlink.integrations')

# Optional: exponential backoff without external deps
_DEFAULT_RETRY_DELAYS = (0.5, 1.0, 2.0)   # seconds between attempts


class IntegrationBase:
    """
    Base for all ad-network / traffic-source integrations.

    Subclasses set:
        integration_name = 'TikTok'         # used in log messages
        default_timeout  = 10               # seconds (override if needed)

    Then call:
        response = self._post(url, payload, headers={...})
        response = self._get(url, params={...})
    """

    integration_name: str = 'Integration'
    default_timeout:  int = 10
    max_retries:      int = 3

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _post(
        self,
        url:      str,
        payload:  Dict[str, Any],
        *,
        headers:  Optional[Dict[str, str]] = None,
        timeout:  Optional[int] = None,
        retries:  int = 3,
    ) -> Any:
        """
        POST with retry + timeout + structured logging.
        Returns the parsed JSON response dict or raises on final failure.
        """
        return self._request('POST', url, json=payload,
                             headers=headers, timeout=timeout, retries=retries)

    def _get(
        self,
        url:     str,
        *,
        params:  Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        retries: int = 3,
    ) -> Any:
        """GET with retry + timeout + structured logging."""
        return self._request('GET', url, params=params,
                             headers=headers, timeout=timeout, retries=retries)

    def _request(
        self,
        method:  str,
        url:     str,
        *,
        json:    Optional[Dict] = None,
        params:  Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[int]  = None,
        retries: int             = 3,
    ) -> Any:
        """
        Core HTTP request with exponential-backoff retry.

        Logs:
            INFO  — successful send (method, url, status, duration_ms)
            WARNING — retryable failure (attempt N of M)
            ERROR — final failure after all retries exhausted
        """
        import requests as _req

        timeout  = timeout or self.default_timeout
        retries  = min(retries, self.max_retries)
        delays   = _DEFAULT_RETRY_DELAYS[:retries]
        last_exc = None

        for attempt, delay in enumerate(delays + (None,), start=1):
            t0 = time.monotonic()
            try:
                resp = _req.request(
                    method, url,
                    json=json, params=params,
                    headers=headers or {},
                    timeout=timeout,
                )
                duration_ms = round((time.monotonic() - t0) * 1000)
                resp.raise_for_status()
                logger.info(
                    f"{self.integration_name} {method} {url} → "
                    f"{resp.status_code} ({duration_ms}ms)"
                )
                try:
                    return resp.json()
                except ValueError:
                    return {'status_code': resp.status_code, 'text': resp.text}

            except _req.exceptions.HTTPError as exc:
                duration_ms = round((time.monotonic() - t0) * 1000)
                status = exc.response.status_code if exc.response else '?'
                # 4xx errors are NOT retried — they indicate a client-side issue
                if exc.response and 400 <= exc.response.status_code < 500:
                    logger.error(
                        f"{self.integration_name} {method} {url} → "
                        f"HTTP {status} (client error, not retrying): {exc}"
                    )
                    raise
                logger.warning(
                    f"{self.integration_name} {method} {url} → "
                    f"HTTP {status} attempt {attempt}/{len(delays)+1} ({duration_ms}ms): {exc}"
                )
                last_exc = exc

            except (_req.exceptions.Timeout,
                    _req.exceptions.ConnectionError) as exc:
                duration_ms = round((time.monotonic() - t0) * 1000)
                logger.warning(
                    f"{self.integration_name} {method} {url} → "
                    f"{exc.__class__.__name__} attempt {attempt}/{len(delays)+1} ({duration_ms}ms)"
                )
                last_exc = exc

            except Exception as exc:
                logger.error(
                    f"{self.integration_name} {method} {url} → "
                    f"Unexpected error: {exc}"
                )
                raise

            if delay is not None:
                time.sleep(delay)

        # All retries exhausted
        logger.error(
            f"{self.integration_name} {method} {url} → "
            f"Failed after {len(delays)+1} attempts. Last error: {last_exc}"
        )
        raise last_exc

    # ── Fire-and-forget helper (non-blocking, best-effort) ────────────────────

    def _fire_and_forget(
        self,
        url:     str,
        payload: Dict[str, Any],
        *,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Best-effort POST — logs warning on failure but never raises.
        Use for pixel-fire / impression-level events where delivery
        failure is acceptable.
        """
        try:
            self._post(url, payload, headers=headers, retries=1)
        except Exception as exc:
            logger.warning(
                f"{self.integration_name} fire-and-forget {url} → "
                f"failed (suppressed): {exc}"
            )
