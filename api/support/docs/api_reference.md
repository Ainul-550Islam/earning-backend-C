# API Reference

## Base URL: `/api/support/`

### Settings
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `settings/` | Public | Get support settings |
| PATCH | `settings/` | Admin | Update settings |

### Tickets
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `tickets/` | Agent | List tickets |
| POST | `tickets/` | User | Create ticket |
| GET | `tickets/{id}/` | Owner/Agent | Ticket detail + thread |
| PATCH | `tickets/{id}/` | Agent | Update ticket |
| POST | `tickets/{id}/reply/` | Owner/Agent | Add reply |
| POST | `tickets/{id}/resolve/` | Agent | Resolve ticket |
| POST | `tickets/{id}/close/` | Owner/Agent | Close ticket |
| POST | `tickets/{id}/rate/` | Owner | CSAT rating |
| POST | `tickets/{id}/assign/` | Agent | Assign to agent |
| POST | `tickets/{id}/escalate/` | Agent | Escalate |
| GET | `tickets/stats/` | Admin | Dashboard stats |

### FAQs
| GET | `faqs/` | Public | List FAQs |
| POST | `faqs/{id}/helpful/` | User | Vote helpful |

### Live Chat
| POST | `chat/start/` | User | Start chat session |
| GET | `chat/{session_id}/` | Owner/Agent | Chat detail |
| POST | `chat/{session_id}/message/` | Owner/Agent | Send message |
| POST | `chat/{session_id}/end/` | Any | End session |

### Knowledge Base
| GET | `kb/categories/` | Public | List categories |
| GET | `kb/articles/` | Public | List/search articles |
| GET | `kb/articles/{slug}/` | Public | Article detail |

### Dashboard
| GET | `dashboard/` | Admin | Full dashboard |
| GET | `portal/` | User | Self-service portal |

### CPA
| POST | `dispute/offer/` | User | Submit offer dispute |
| GET | `dispute/my/` | User | My disputes |
