# Support System API Documentation

## Base URL
`/api/support/`

## Authentication
All endpoints require JWT or Token authentication unless marked as public.

## Original Endpoints (Preserved)
| Method | URL | Description |
|--------|-----|-------------|
| GET | `settings/` | Get support settings (public) |
| GET/POST | `tickets/` | List/create tickets |
| GET/PATCH | `tickets/{id}/` | Get/update ticket |
| PATCH | `tickets/{id}/respond/` | Agent respond (admin) |
| GET | `tickets/stats/` | Statistics (admin) |
| GET/POST | `faqs/` | List/create FAQs |
| GET/PATCH/DELETE | `faqs/{id}/` | FAQ detail |

## New Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| POST | `tickets/{id}/reply/` | Add message |
| POST | `tickets/{id}/resolve/` | Resolve ticket |
| POST | `tickets/{id}/rate/` | CSAT rating |
| POST | `tickets/{id}/escalate/` | Escalate |
| GET | `tickets/{id}/sla/` | SLA status |
| POST | `tickets/{id}/attach/` | Upload attachment |
| POST | `faqs/{id}/helpful/` | Helpful vote |
| GET | `kb/categories/` | KB categories |
| GET | `kb/articles/` | KB articles |
| POST | `chat/start/` | Start live chat |
| POST | `dispute/offer/` | Offer dispute |
| POST | `dispute/withdrawal/` | Withdrawal dispute |
| GET | `announcements/` | Network announcements |
| GET | `dashboard/` | Agent dashboard |
| GET | `portal/` | User portal |

## WebSocket Endpoints
- `ws/support/chat/{session_id}/` — Live chat
- `ws/support/agent/` — Agent dashboard
- `ws/support/notifications/` — User notifications

## Webhook Endpoints (Incoming)
- `POST webhooks/offer-completed/` — Offerwall completion
- `POST webhooks/fraud-alert/` — Fraud detection alert
