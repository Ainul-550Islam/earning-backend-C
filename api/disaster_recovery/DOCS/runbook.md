# DR Runbook

## Database Failover
1. Detect primary failure via monitoring alert
2. Verify replica health: `python scripts/health_check.py`
3. Promote replica: `pg_ctl promote -D /var/lib/postgresql/data`
4. Update DNS: point db.example.com to replica IP
5. Verify application connectivity
6. Create incident report

## Emergency Restore
```bash
python scripts/emergency_restore.py --database mydb --confirm
```
