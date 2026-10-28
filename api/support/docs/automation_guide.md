# Automation Engine Guide

## How It Works
1. **Trigger** fires (e.g., ticket_created)
2. **Conditions** evaluated (AND/OR)
3. **Actions** executed if conditions match

## Triggers
- `ticket_created`, `ticket_updated`, `ticket_status_changed`
- `reply_received`, `agent_replied`
- `sla_warning`, `sla_breach`
- `ticket_idle_1h`, `ticket_idle_24h`, `ticket_idle_72h`
- `ticket_escalated`, `ticket_resolved`, `manual`

## Conditions (field / operator / value)
- `priority` equals `urgent`
- `category` equals `payment`
- `status` equals `open`
- `tags` contains `vip`
- `escalated` equals `true`

## Actions
- `assign_to` — agent_id
- `set_priority` — urgent/high/medium/low
- `set_status` — in_progress/resolved/closed
- `add_tag` — tag_name
- `send_reply` — message text
- `escalate` — true
- `send_notification` — email/telegram/slack

## Example Rule
Condition: `priority=urgent AND status=open`
Action: `assign_to=supervisor, send_notification=telegram`
