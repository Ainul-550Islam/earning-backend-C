# Troubleshooting Guide

## Common Issues

### Postback Rejected: "No signature provided"
- Check if network is sending `X-Postback-Signature` header or `&sig=` param
- Verify `signature_algorithm` matches network's signing method
- Set `signature_algorithm=none` for networks without HMAC

### Postback Rejected: "IP not whitelisted"
- Add network's server IP to `ip_whitelist` in AdNetworkConfig
- Clear IP whitelist cache: `ip_whitelist_manager.invalidate_cache(network)`

### Duplicate postback not detected
- Check Redis is running: `redis-cli ping`
- Verify dedup TTL hasn't expired (default: 30 days)
- Check `ConversionDeduplication` table for the lead_id

### Conversion created but wallet not credited
- Check `RetryLog` for failed wallet credit attempts
- Run: `python manage.py shell -c "from api.postback_engine.queue_management.batch_processor import batch_processor; batch_processor.replay_failed()"`
- Check `CELERY_BROKER_URL` is set correctly

### High fraud false-positives
- Increase `FRAUD_FLAG_THRESHOLD` in settings
- Check if network's server IPs are datacenter IPs (expected)
- Whitelist specific IPs: add to `ip_whitelist` field

### Queue depth growing
- Check Celery worker is running: `celery -A config worker`
- Check worker logs for errors
- Run: `python api/postback_engine/scripts/monitor_queue.py`

## Diagnostic Commands

```bash
# Check queue depth
python manage.py shell -c "from api.postback_engine.queue_management.queue_manager import queue_manager; print(queue_manager.get_stats())"

# Check realtime stats
python manage.py shell -c "from api.postback_engine.analytics_reporting.real_time_dashboard import realtime_dashboard; print(realtime_dashboard.get_live_stats())"

# Health check
python api/postback_engine/scripts/health_check.py

# Sync networks
python api/postback_engine/scripts/sync_networks.py

# Replay failed postbacks
python api/postback_engine/scripts/replay_failed.py --limit 100
```
