# Ticket System Guide

## Ticket Lifecycle
```
open → in_progress → waiting_user ↔ in_progress → resolved → closed
                                                 ↘ spam
```

## Priority & SLA
| Priority | First Response | Resolution |
|----------|---------------|------------|
| urgent   | 1 hour        | 4 hours    |
| high     | 4 hours       | 24 hours   |
| medium   | 8 hours       | 48 hours   |
| low      | 24 hours      | 72 hours   |

## Auto-Classification
Categories auto-classify to priority via `CATEGORY_PRIORITY_MAP` in `choices.py`.

## Ticket Thread
Each ticket has a message thread (`TicketMessage`). Agents can mark messages as internal notes (hidden from users).

## SLA Tracking
`TicketSLA` model tracks deadlines. Celery checks every 15 minutes via `check_sla_breaches` task.

## Automation
Rules in `AutomationRule` fire on triggers like `ticket_created`, `ticket_idle_24h`, `sla_breach`.
