# Backup Policy

## Backup Schedule
| Type | Frequency | Retention | Storage |
|------|-----------|-----------|----------|
| Full | Weekly (Sun 02:00) | 30 days | S3 + Glacier |
| Differential | Daily (02:00) | 14 days | S3 |
| Incremental | Hourly | 7 days | S3 |
| Snapshot | Every 6h | 2 days | EBS |

## Encryption
All backups encrypted with AES-256-GCM.
