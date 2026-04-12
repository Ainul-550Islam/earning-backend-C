# How SmartLink Redirect Works

## Full Flow (< 5ms target)

```
1. Browser visits: https://go.example.com/abc123/?sub1=camp1
                                ↓
2. Nginx (< 1ms)
   - Rate limit check (1000 req/min per IP)
   - Proxy to Django (keepalive connection)
                                ↓
3. SmartLinkRedirectMiddleware (< 0.5ms)
   - Check Redis: sl:abc123:simple → cache hit?
   - If hit + no targeting: return instant redirect
                                ↓
4. PublicRedirectView (< 1ms)
   - Extract IP, User-Agent
   - GeoIPEnricher.enrich(ip) → country, ISP, ASN (cached)
   - DeviceTargetingService.parse_user_agent(ua) → device, OS, browser
   - Build request_context dict
                                ↓
5. SmartLinkResolverService.resolve(slug, context) (< 2ms)
   │
   ├─ A. SmartLinkCacheService.get_smartlink(slug)
   │     → Redis GET sl:abc123 (< 0.3ms)
   │     → DB fallback if miss → cache for 5 min
   │
   ├─ B. BotDetectionService.detect(ip, ua) (< 0.1ms)
   │     → 15 UA pattern checks
   │     → Headless browser detection
   │     → If bot → fallback URL (no offer shown)
   │
   ├─ C. ClickFraudService.score(ip, ua, context) (< 0.5ms)
   │     + FraudMLScorer.score_click() (20-signal ML)
   │     → score 0-100, signals list
   │     → score >= 85: block (HTTP 403)
   │     → score >= 60: flag (still redirect)
   │
   ├─ D. TargetingEngine.evaluate(smartlink, context) (< 0.5ms)
   │     → GeoTargeting: country/region/city match
   │     → DeviceTargeting: mobile/tablet/desktop
   │     → OSTargeting: android/ios/windows
   │     → TimeTargeting: day+hour check
   │     → ISPTargeting: carrier match
   │     → LanguageTargeting: accept-language
   │     → AND/OR logic combination
   │     → Returns: eligible OfferPoolEntry list
   │
   ├─ E. OfferRotationService.select(entries, context) (< 0.3ms)
   │     → Filter capped entries (Redis cap check)
   │     → SmartRotationMLEngine.select_offer() [Thompson Sampling]
   │     → OR: Weighted random / EPC-optimized / Priority
   │     → Returns: winning OfferPoolEntry
   │
   └─ F. URLBuilderService.build(offer, smartlink, context) (< 0.1ms)
         → Append sub1-sub5, sl_id, geo, device to offer URL
         → Returns: final redirect URL
                                ↓
6. RedirectService.build_response(result) (< 0.1ms)
   → HTTP 302 response with headers:
     Location: https://offer.example.com/?sub1=camp1&sl_id=abc123&geo=US&...
     X-Robots-Tag: noindex, nofollow
     Cache-Control: no-store
     X-SmartLink-Time: 3.21ms
                                ↓
7. Celery (async, non-blocking)
   ├─ process_click_async.delay() → DB write
   ├─ ClickDeduplicationService → UniqueClick record
   ├─ ClickTrackingService → Click + ClickMetadata
   └─ log_redirect_async.delay() → RedirectLog record
```

## Performance Breakdown

| Step | Target | Technology |
|---|---|---|
| Nginx proxy | < 0.5ms | nginx keepalive |
| Middleware cache hit | < 0.5ms | Redis GET |
| GeoIP lookup | < 0.3ms | Redis cached enrichment |
| Fraud scoring | < 0.5ms | Redis counters |
| Targeting eval | < 0.5ms | Cached rules |
| Offer rotation | < 0.3ms | Thompson Sampling |
| URL build | < 0.1ms | Python string ops |
| **Total** | **< 5ms** | **Full pipeline** |

## Cache Strategy

```
Redis Key                    TTL      Content
─────────────────────────────────────────────────────
sl:{slug}                    5 min    Full SmartLink object
sl:{slug}:simple             60s      Direct URL (no targeting)
sl_pool:{smartlink_id}       60s      OfferPoolEntry list
sl_targeting:{smartlink_id}  10 min   TargetingRule + sub-rules
offer_score:{id}:{geo}:{dev} 30 min   EPC score
cap:daily:{entry_id}:{date}  1 hour   Daily click counter
geoip:{ip}                   1 hour   Full IP enrichment
fraud:blocked:{ip}           24 hours Blocked IP flag
ml_bandit:{offer}:{context}  1 hour   Thompson Sampling params
```
