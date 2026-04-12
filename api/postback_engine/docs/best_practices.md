# Best Practices

## Security

1. **Always use HMAC signatures** — Never run networks with `signature_algorithm=none` in production
2. **IP whitelist all networks** — Get server IP list from each network and add to whitelist
3. **Rotate secret keys quarterly** — Use `api_key_manager.generate()` for new keys
4. **Enable rate limiting** — Set `rate_limit_per_minute` on each network config
5. **Monitor fraud dashboard daily** — Review FraudAttemptLog for unusual patterns

## Performance

1. **Use Redis cache** — All velocity/dedup checks use Redis — ensure it's fast
2. **Configure Celery concurrency** — Set `CELERY_WORKER_CONCURRENCY` based on CPU cores
3. **Set up DB indexes** — All models have proper indexes — run `python manage.py migrate`
4. **Monitor queue depth** — Alert if queue depth exceeds 1000 items
5. **Archive old logs** — Run `cleanup_logs.py` weekly with 90-day retention

## Business Rules

1. **Set conversion windows** — Always set `conversion_window_hours` (recommended: 720 = 30 days)
2. **Configure reward rules** — Set `reward_rules` per offer to control per-offer payout
3. **Enable test mode first** — Set `is_test_mode=True` for new networks, disable after validation
4. **Monitor deduplication** — Check `ConversionDeduplication` table size monthly
5. **Review reversals** — Any network with > 5% reversal rate should be investigated

## Monitoring

1. **Set up Slack alerts** — Configure `SLACK_WEBHOOK_URL` for daily reports
2. **Monitor `PostbackRawLog.status`** — High `FAILED` count indicates issues
3. **Track `conversion_rate`** in NetworkPerformance — Drops > 50% need investigation
4. **Check `fraud_rate`** daily — Spikes indicate bot attacks
5. **Review dead letter queue weekly** — Use `dead_letter_queue.py` to process stuck items
