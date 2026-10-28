# CMS API Route Map

All routes live under the base URL configured in the Django URL conf.
DRF router generates `list`, `create`, `retrieve`, `update`, `partial_update`,
`destroy` automatically. Custom `@action` endpoints are listed explicitly.

Legend:
- 🔓 IsAuthenticated
- 🔒 IsAdminUser
- 🌐 AllowAny

---

## v1 / v2 — Legacy (preserved, no changes)

| Method | URL | View | Auth |
|--------|-----|------|------|
| GET/POST | `categories/` | ContentCategoryViewSet | 🔒 |
| GET/POST | `pages/` | ContentPageViewSet | 🔒 |
| GET/POST | `faq-categories/` | FAQCategoryViewSet | 🔒 |
| GET/POST | `faqs/` | FAQViewSet | 🔒 |
| GET/POST | `galleries/` | ImageGalleryViewSet | 🔒 |
| GET/POST | `gallery-images/` | GalleryImageViewSet | 🔒 |
| GET/POST | `files/` | FileManagerViewSet | 🔒 |
| GET/POST | `comments/` | CommentViewSet | 🔓 |
| GET/POST | `settings/` | SiteSettingsViewSet | 🔒 |
| GET/POST | `permissions/` | ContentPermissionViewSet | 🔒 |
| GET/POST | `v2/pages/` | PageViewSet | 🔒 |

---

## v3 — Survey System

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/survey-categories/` | List categories | 🔓 |
| GET | `v3/survey-templates/` | List surveys | 🔓 |
| GET | `v3/survey-templates/{id}/active/` | Active surveys for user | 🔓 |
| GET | `v3/survey-questions/` | Questions (filterable by survey) | 🔓 |
| GET/POST | `v3/survey-completions/` | Start / list completions | 🔓 |
| PATCH | `v3/survey-completions/{id}/` | Update completion | 🔓 |
| POST | `v3/survey-completions/{id}/approve/` | Admin approve | 🔒 |
| GET/POST | `v3/survey-responses/` | Submit answers | 🔓 |
| GET | `v3/survey-rewards/` | Reward configs | 🔓 |
| GET | `v3/reward-transactions/` | Own transaction ledger | 🔓 |
| POST | `v3/reward-transactions/{uuid}/approve/` | Admin approve | 🔒 |
| GET | `v3/reward-pools/` | Reward pool budgets | 🔒 |

---

## v3 — Survey Analytics  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/survey-analytics/overview/?days=30` | Platform dashboard | 🔒 |
| GET | `v3/survey-analytics/realtime/` | Live metrics | 🔒 |
| GET | `v3/survey-analytics/survey/{uuid}/report/?days=30` | Per-survey report | 🔒 |
| GET | `v3/survey-analytics/user/{user_id}/?days=30` | Per-user (admin) | 🔒 |
| GET | `v3/survey-analytics/me/?days=30` | Own analytics | 🔓 |

---

## v3 — User Profile & Segmentation

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET/PATCH | `v3/user-profiles/{id}/` | Profile CRUD | 🔓 |
| GET | `v3/user-profiles/me/` | Own profile | 🔓 |
| GET | `v3/user-segments/` | List segments | 🔒 |
| POST | `v3/user-segments/{id}/evaluate/` | Check if user matches | 🔒 |

---

## v3 — Task Management

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET/POST | `v3/task-schedules/` | Schedule CRUD | 🔒 |
| POST | `v3/task-schedules/{id}/trigger/` | Manual trigger | 🔒 |
| GET | `v3/task-executions/` | Execution history | 🔒 |
| GET | `v3/task-queue/` | Pending queue | 🔒 |
| GET | `v3/task-locks/` | Active locks | 🔒 |

---

## v3 — A/B Testing

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET/POST | `v3/ab-tests/` | Test management | 🔒 |
| GET/POST | `v3/ab-variants/` | Variant config | 🔒 |
| GET | `v3/ab-participants/` | Participation log | 🔒 |
| GET | `v3/ab-results/` | Conversion results | 🔒 |
| GET | `v3/ab-analytics/` | Aggregated stats | 🔒 |

---

## v3 — Real-time Offers

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/realtime-offers/` | Live offer list | 🔓 |
| GET/POST | `v3/offer-subscriptions/` | User subscriptions | 🔓 |
| GET | `v3/offer-updates/` | Update queue | 🔓 |
| GET | `v3/realtime-offer-updates/` | SSE update log | 🔒 |

---

## v3 — Content Structure  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/banner-rewards/` | Own banner rewards | 🔓 |
| GET | `v3/banner-rewards/summary/` | Aggregated totals | 🔓 |
| GET/POST | `v3/block-definitions/` | Block type CRUD | 🔒 |
| GET | `v3/block-definitions/active/` | Active blocks for editor | 🔓 |
| GET/POST | `v3/content-schedules/` | Publication schedules | 🔒 |
| GET | `v3/content-schedules/pending/` | Due within 24h | 🔒 |
| POST | `v3/content-schedules/{id}/cancel/` | Cancel a schedule | 🔒 |

---

## v3 — Forms  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/dynamic-forms/` | Form list | 🔓 |
| GET | `v3/dynamic-forms/{id}/fields/` | Fields for a form | 🔓 |
| GET/POST | `v3/form-fields/` | Field CRUD (admin) | 🔒 |
| GET/POST | `v3/form-submissions/` | Submit / list submissions | 🔓 |

---

## v3 — Leaderboard & Streak  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/leaderboard-periods/` | All periods | 🔓 |
| GET | `v3/leaderboard-periods/current/` | Active period | 🔓 |
| GET | `v3/leaderboard-entries/?period=<id>` | Ranked entries | 🔓 |
| GET | `v3/leaderboard-entries/my_rank/` | Caller's rank | 🔓 |
| GET | `v3/leaderboard-entries/top/?n=10` | Top N entries | 🔓 |
| GET | `v3/earning-streaks/my_streak/` | Own streak | 🔓 |
| GET | `v3/streak-milestones/` | Milestone list | 🔓 |

---

## v3 — CPAlead Extras  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/locker-unlocks/` | Own unlock history | 🔓 |
| GET | `v3/offer-cache/` | Cached offers | 🔓 |
| POST | `v3/offer-cache/refresh/` | Force refresh from API | 🔒 |
| GET | `v3/virtual-transactions/` | Own ledger | 🔓 |
| GET | `v3/virtual-transactions/balance/` | Current balance | 🔓 |
| GET | `v3/zero-hours-logs/` | Session history | 🔓 |

---

## v3 — Quiz  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET/POST | `v3/quiz-questions/` | Question CRUD | 🔒 |
| GET/POST | `v3/quiz-answers/` | Answer CRUD | 🔒 |
| GET | `v3/quiz-results/` | Result configs | 🔒 |
| GET/POST | `v3/quiz-attempts/` | Start attempt | 🔓 |
| POST | `v3/quiz-attempts/{id}/complete/` | Finalise + reward | 🔓 |

---

## v3 — RTB  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET/POST | `v3/rtb-ad-slots/` | Slot CRUD | 🔒 |
| GET | `v3/rtb-ad-slots/active/` | Active slots | 🔓 |
| GET | `v3/rtb-bid-logs/` | Bid log | 🔒 |

---

## v3 — Referral  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/referral-codes/mine/` | Own code (auto-creates) | 🔓 |
| GET | `v3/referral-relationships/` | Referred users | 🔓 |
| GET | `v3/referral-earnings/` | Earning history | 🔓 |
| GET | `v3/referral-earnings/totals/` | Aggregate totals | 🔓 |

---

## v3 — SmartLink  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET/POST | `v3/smartlink-rules/` | Rule CRUD | 🔒 |
| GET | `v3/smartlink-clicks/` | Click analytics | 🔒 |

---

## v3 — Video  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/video-gen-requests/` | Generation queue | 🔒 |

---

## v3 — Workflow  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET/POST | `v3/workflow-rules/` | Rule CRUD | 🔒 |
| GET/POST | `v3/workflow-states/` | State management | 🔓 |
| POST | `v3/workflow-states/{id}/transition/` | State change + audit | 🔓 |
| GET | `v3/workflow-transitions/` | Audit trail | 🔓 |

---

## v3 — Permissions Audit  *(previously zero API exposure)*

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/permission-audit-logs/` | Audit trail | 🔒 |
| GET | `v3/permission-stats/` | Usage stats | 🔒 |

---

## v3 — CMS Operations  *(previously zero API exposure)*

### Publish (`v3/cms-publish/`)

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| POST | `v3/cms-publish/publish/` | Publish one object | 🔒 |
| POST | `v3/cms-publish/unpublish/` | Unpublish | 🔒 |
| POST | `v3/cms-publish/bulk_publish/` | Publish list of IDs | 🔒 |
| POST | `v3/cms-publish/run_scheduled/` | Sweep due schedules | 🔒 |

### Cache (`v3/cms-cache/`)

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| POST | `v3/cms-cache/clear_all/` | Wipe all CMS caches | 🔒 |
| POST | `v3/cms-cache/warm/` | Pre-warm blog cache | 🔒 |
| POST | `v3/cms-cache/invalidate/` | Invalidate by type+id | 🔒 |

### Editorial Calendar (`v3/content-calendar/`)

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| GET | `v3/content-calendar/upcoming/?days=30` | Upcoming items | 🔓 |
| GET | `v3/content-calendar/month/?year=2026&month=6` | Monthly calendar | 🔓 |
| POST | `v3/content-calendar/schedule/` | Schedule new item | 🔒 |
| POST | `v3/content-calendar/cancel/` | Cancel schedule | 🔒 |
| POST | `v3/content-calendar/process_due/` | Run due schedules | 🔒 |

### Misc (`v3/misc/`)

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| POST | `v3/misc/process_reward/` | Process BannerReward | 🔓 |
| POST | `v3/misc/retry_failed_rewards/` | Retry failed rewards | 🔒 |
| GET | `v3/misc/my_rewards/` | Own reward list | 🔓 |
| POST | `v3/misc/reorder_blocks/` | Reorder block types | 🔒 |
| POST | `v3/misc/comment_reaction/` | Toggle reaction | 🔓 |
| GET | `v3/misc/comment_reaction_counts/` | Reaction counts | 🔓 |
| GET | `v3/misc/check_permission/` | Permission check | 🔓 |
| POST | `v3/misc/grant_permission/` | Grant permission | 🔒 |
| POST | `v3/misc/revoke_permission/` | Revoke permission | 🔒 |
| POST | `v3/misc/publish_landing_page/` | Publish landing page | 🔒 |
| GET | `v3/misc/audit_log/` | Audit log | 🔒 |

---

## Webhooks

| Method | URL | Notes | Auth |
|--------|-----|-------|------|
| POST | `webhooks/cpalead/` | CPAlead postback v1 | 🌐 |
| POST | `webhooks/cpalead/v2/` | CPAlead postback v2 | 🌐 |
| POST | `webhooks/<source>/` | Generic webhook | 🌐 |
| POST | `callbacks/wallet/` | Wallet callback | 🌐 |
| GET | `health/` | Health check | 🌐 |
| GET | `integration/status/` | Integration status | 🔒 |

---

*Total registered routes: 124 DRF router registrations + 6 path() entries*
