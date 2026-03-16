import client from "../client";

// ─────────────────────────────────────────────────────────────────
//  ContentCategory Model → /api/cms/categories/
// ─────────────────────────────────────────────────────────────────
export const contentCategoryAPI = {
  // GET    /api/cms/categories/
  // params: { category_type, is_active, show_in_menu, show_in_app,
  //           parent, page }
  list: (params = {}) =>
    client.get("/cms/categories/", { params }),

  // GET    /api/cms/categories/:id/
  detail: (id) =>
    client.get(`/cms/categories/${id}/`),

  // POST   /api/cms/categories/
  create: (data) =>
    client.post("/cms/categories/", data),

  // PATCH  /api/cms/categories/:id/
  update: (id, data) =>
    client.patch(`/cms/categories/${id}/`, data),

  // DELETE /api/cms/categories/:id/
  delete: (id) =>
    client.delete(`/cms/categories/${id}/`),

  // GET    /api/cms/categories/:id/breadcrumbs/
  // triggers: get_breadcrumbs() with caching
  breadcrumbs: (id) =>
    client.get(`/cms/categories/${id}/breadcrumbs/`),

  // GET    /api/cms/categories/:id/children/
  // triggers: get_active_children()
  children: (id) =>
    client.get(`/cms/categories/${id}/children/`),

  // POST   /api/cms/categories/:id/increment_view/
  // triggers: increment_view_count() atomically
  incrementView: (id) =>
    client.post(`/cms/categories/${id}/increment_view/`),
};

// ─────────────────────────────────────────────────────────────────
//  ContentPage Model → /api/cms/pages/
//  Custom Manager: ContentPageManager
//    .published() → status=published&is_active=true
//    .featured()  → is_featured=true
//    .by_category(slug) → category__slug
//    .by_type(type) → page_type
//    .scheduled() → status=scheduled
//    .expired()   → expired
// ─────────────────────────────────────────────────────────────────
export const contentPageAPI = {
  // GET    /api/cms/pages/
  // params: { status, page_type, category, is_featured, is_pinned,
  //           visibility, language, author, page }
  list: (params = {}) =>
    client.get("/cms/pages/", { params }),

  // GET    /api/cms/pages/:slug/  (UUID or slug)
  detail: (slug) =>
    client.get(`/cms/pages/${slug}/`),

  // POST   /api/cms/pages/
  create: (data) =>
    client.post("/cms/pages/", data),

  // PATCH  /api/cms/pages/:slug/
  update: (slug, data) =>
    client.patch(`/cms/pages/${slug}/`, data),

  // DELETE /api/cms/pages/:slug/
  delete: (slug) =>
    client.delete(`/cms/pages/${slug}/`),

  // GET    /api/cms/pages/stats/
  stats: () =>
    client.get("/cms/pages/stats/"),

  // ─── ContentPageManager methods ───

  // GET    /api/cms/pages/?status=published&is_active=true
  published: (params = {}) =>
    client.get("/cms/pages/", { params: { ...params, status: "published", is_active: true } }),

  // GET    /api/cms/pages/?is_featured=true
  featured: (params = {}) =>
    client.get("/cms/pages/", { params: { ...params, is_featured: true } }),

  // GET    /api/cms/pages/?status=scheduled
  scheduled: (params = {}) =>
    client.get("/cms/pages/", { params: { ...params, status: "scheduled" } }),

  // GET    /api/cms/pages/?status=expired
  expired: (params = {}) =>
    client.get("/cms/pages/", { params: { ...params, status: "expired" } }),

  // ─── Instance methods ───

  // POST   /api/cms/pages/:slug/increment_view/
  incrementView: (slug) =>
    client.post(`/cms/pages/${slug}/increment_view/`),

  // POST   /api/cms/pages/:slug/increment_share/
  incrementShare: (slug) =>
    client.post(`/cms/pages/${slug}/increment_share/`),

  // POST   /api/cms/pages/:slug/increment_like/
  incrementLike: (slug) =>
    client.post(`/cms/pages/${slug}/increment_like/`),

  // POST   /api/cms/pages/:slug/create_version/
  // triggers: create_new_version() backend method
  createVersion: (slug) =>
    client.post(`/cms/pages/${slug}/create_version/`),

  // GET    /api/cms/pages/:slug/version_history/
  // triggers: get_version_history() backend method
  versionHistory: (slug) =>
    client.get(`/cms/pages/${slug}/version_history/`),

  // GET    /api/cms/pages/:slug/related/
  // triggers: get_related_content() with caching
  // params: { limit }
  related: (slug, limit = 5) =>
    client.get(`/cms/pages/${slug}/related/`, { params: { limit } }),

  // POST   /api/cms/pages/bulk_increment_views/
  // triggers: bulk_increment_views() classmethod
  // body: { ids: [...] }
  bulkIncrementViews: (ids) =>
    client.post("/cms/pages/bulk_increment_views/", { ids }),
};

// ─────────────────────────────────────────────────────────────────
//  Banner Model → /api/cms/banners/
//  Custom Manager: BannerManager
//    .active_banners()       → is_active+date filtered
//    .get_for_position()     → position+device filtered
//    .get_rotating_banners() → priority+impressions sorted
// ─────────────────────────────────────────────────────────────────
export const bannerAPI = {
  // GET    /api/cms/banners/
  // params: { banner_type, position, is_active, target_device, page }
  list: (params = {}) =>
    client.get("/cms/banners/", { params }),

  // GET    /api/cms/banners/:id/
  detail: (id) =>
    client.get(`/cms/banners/${id}/`),

  // POST   /api/cms/banners/
  create: (data) =>
    client.post("/cms/banners/", data),

  // PATCH  /api/cms/banners/:id/
  update: (id, data) =>
    client.patch(`/cms/banners/${id}/`, data),

  // DELETE /api/cms/banners/:id/
  delete: (id) =>
    client.delete(`/cms/banners/${id}/`),

  // GET    /api/cms/banners/stats/
  stats: () =>
    client.get("/cms/banners/stats/"),

  // GET    /api/cms/banners/active/
  // triggers: active_banners() BannerManager method
  active: (params = {}) =>
    client.get("/cms/banners/active/", { params }),

  // GET    /api/cms/banners/by_position/
  // triggers: get_for_position() / get_rotating_banners()
  // params: { position, device, limit }
  byPosition: (position, device = "all", limit = 5) =>
    client.get("/cms/banners/by_position/", { params: { position, device, limit } }),

  // POST   /api/cms/banners/:id/record_impression/
  // triggers: record_impression() backend method
  recordImpression: (id) =>
    client.post(`/cms/banners/${id}/record_impression/`),

  // POST   /api/cms/banners/:id/record_click/
  // triggers: record_click() + award_reward() backend methods
  recordClick: (id) =>
    client.post(`/cms/banners/${id}/record_click/`),

  // POST   /api/cms/banners/bulk_impressions/
  // triggers: bulk_record_impressions() BannerManager method
  // body: { banner_ids: [...] }
  bulkImpressions: (bannerIds) =>
    client.post("/cms/banners/bulk_impressions/", { banner_ids: bannerIds }),
};

// ─────────────────────────────────────────────────────────────────
//  FAQCategory Model → /api/cms/faq-categories/
// ─────────────────────────────────────────────────────────────────
export const faqCategoryAPI = {
  // GET    /api/cms/faq-categories/
  // params: { faq_type, is_active, page }
  list: (params = {}) =>
    client.get("/cms/faq-categories/", { params }),

  // GET    /api/cms/faq-categories/:id/
  detail: (id) =>
    client.get(`/cms/faq-categories/${id}/`),

  // POST   /api/cms/faq-categories/
  create: (data) =>
    client.post("/cms/faq-categories/", data),

  // PATCH  /api/cms/faq-categories/:id/
  update: (id, data) =>
    client.patch(`/cms/faq-categories/${id}/`, data),

  // DELETE /api/cms/faq-categories/:id/
  delete: (id) =>
    client.delete(`/cms/faq-categories/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  FAQ Model → /api/cms/faqs/
//  Custom Manager: FAQManager
//    .published() → is_active=true
//    .featured()  → is_featured=true
//    .popular()   → ordered by view_count
//    .search(q)   → question/answer search
//    .by_tags()   → tag match
// ─────────────────────────────────────────────────────────────────
export const faqAPI = {
  // GET    /api/cms/faqs/
  // params: { category, is_active, is_featured, is_pinned,
  //           show_in_app, show_on_website, page }
  list: (params = {}) =>
    client.get("/cms/faqs/", { params }),

  // GET    /api/cms/faqs/:slug/
  detail: (slug) =>
    client.get(`/cms/faqs/${slug}/`),

  // POST   /api/cms/faqs/
  create: (data) =>
    client.post("/cms/faqs/", data),

  // PATCH  /api/cms/faqs/:slug/
  update: (slug, data) =>
    client.patch(`/cms/faqs/${slug}/`, data),

  // DELETE /api/cms/faqs/:slug/
  delete: (slug) =>
    client.delete(`/cms/faqs/${slug}/`),

  // GET    /api/cms/faqs/search/?q=...
  // triggers: FAQManager.search() method
  search: (query, params = {}) =>
    client.get("/cms/faqs/search/", { params: { q: query, ...params } }),

  // GET    /api/cms/faqs/popular/?limit=10
  // triggers: FAQManager.popular()
  popular: (limit = 10) =>
    client.get("/cms/faqs/popular/", { params: { limit } }),

  // GET    /api/cms/faqs/?is_featured=true
  // triggers: FAQManager.featured()
  featured: (params = {}) =>
    client.get("/cms/faqs/", { params: { ...params, is_featured: true } }),

  // POST   /api/cms/faqs/:slug/increment_view/
  // triggers: increment_view_count()
  incrementView: (slug) =>
    client.post(`/cms/faqs/${slug}/increment_view/`),

  // POST   /api/cms/faqs/:slug/feedback/
  // triggers: record_feedback() backend method
  // body: { is_helpful, feedback_text }
  feedback: (slug, is_helpful, feedback_text = "") =>
    client.post(`/cms/faqs/${slug}/feedback/`, { is_helpful, feedback_text }),

  // GET    /api/cms/faqs/:slug/related/
  // triggers: get_related_faqs() with caching
  related: (slug, limit = 5) =>
    client.get(`/cms/faqs/${slug}/related/`, { params: { limit } }),
};

// ─────────────────────────────────────────────────────────────────
//  SiteSettings Model → /api/cms/settings/
// ─────────────────────────────────────────────────────────────────
export const siteSettingsAPI = {
  // GET    /api/cms/settings/
  // params: { category, is_public, page }
  list: (params = {}) =>
    client.get("/cms/settings/", { params }),

  // GET    /api/cms/settings/:key/
  // triggers: get_setting() classmethod with caching
  detail: (key) =>
    client.get(`/cms/settings/${key}/`),

  // POST   /api/cms/settings/
  // triggers: set_setting() classmethod
  create: (data) =>
    client.post("/cms/settings/", data),

  // PATCH  /api/cms/settings/:key/
  update: (key, data) =>
    client.patch(`/cms/settings/${key}/`, data),

  // DELETE /api/cms/settings/:key/
  delete: (key) =>
    client.delete(`/cms/settings/${key}/`),

  // GET    /api/cms/settings/public/
  // returns: all is_public=true settings
  publicSettings: () =>
    client.get("/cms/settings/", { params: { is_public: true } }),
};

// ─────────────────────────────────────────────────────────────────
//  ImageGallery Model → /api/cms/galleries/
// ─────────────────────────────────────────────────────────────────
export const imageGalleryAPI = {
  // GET    /api/cms/galleries/
  // params: { category, is_active, is_featured, page }
  list: (params = {}) =>
    client.get("/cms/galleries/", { params }),

  // GET    /api/cms/galleries/:slug/
  detail: (slug) =>
    client.get(`/cms/galleries/${slug}/`),

  // POST   /api/cms/galleries/
  create: (data) =>
    client.post("/cms/galleries/", data),

  // PATCH  /api/cms/galleries/:slug/
  update: (slug, data) =>
    client.patch(`/cms/galleries/${slug}/`, data),

  // DELETE /api/cms/galleries/:slug/
  delete: (slug) =>
    client.delete(`/cms/galleries/${slug}/`),
};

// ─────────────────────────────────────────────────────────────────
//  GalleryImage Model → /api/cms/gallery-images/
// ─────────────────────────────────────────────────────────────────
export const galleryImageAPI = {
  // GET    /api/cms/gallery-images/
  // params: { gallery, is_active, page }
  list: (params = {}) =>
    client.get("/cms/gallery-images/", { params }),

  // GET    /api/cms/gallery-images/:id/
  detail: (id) =>
    client.get(`/cms/gallery-images/${id}/`),

  // POST   /api/cms/gallery-images/  (multipart/form-data)
  create: (formData) =>
    client.post("/cms/gallery-images/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  // PATCH  /api/cms/gallery-images/:id/
  update: (id, data) =>
    client.patch(`/cms/gallery-images/${id}/`, data),

  // DELETE /api/cms/gallery-images/:id/
  delete: (id) =>
    client.delete(`/cms/gallery-images/${id}/`),

  // POST   /api/cms/gallery-images/:id/increment_view/
  incrementView: (id) =>
    client.post(`/cms/gallery-images/${id}/increment_view/`),
};

// ─────────────────────────────────────────────────────────────────
//  FileManager Model → /api/cms/files/
// ─────────────────────────────────────────────────────────────────
export const fileManagerAPI = {
  // GET    /api/cms/files/
  // params: { file_type, is_public, is_active, category, page }
  list: (params = {}) =>
    client.get("/cms/files/", { params }),

  // GET    /api/cms/files/:id/
  detail: (id) =>
    client.get(`/cms/files/${id}/`),

  // POST   /api/cms/files/  (multipart/form-data)
  create: (formData) =>
    client.post("/cms/files/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  // PATCH  /api/cms/files/:id/
  update: (id, data) =>
    client.patch(`/cms/files/${id}/`, data),

  // DELETE /api/cms/files/:id/
  delete: (id) =>
    client.delete(`/cms/files/${id}/`),

  // POST   /api/cms/files/:id/download/
  // triggers: increment_download_count()
  download: (id) =>
    client.post(`/cms/files/${id}/download/`),
};

// ─────────────────────────────────────────────────────────────────
//  Comment Model → /api/cms/comments/
//  Custom Manager: CommentManager
//    .approved()          → is_approved=true
//    .pending()           → is_approved=false
//    .by_content_type()   → content_type+object_id, top-level
//    .with_replies()      → prefetched replies
// ─────────────────────────────────────────────────────────────────
export const commentAPI = {
  // GET    /api/cms/comments/
  // params: { content_type, object_id, is_approved, is_flagged,
  //           user, page }
  list: (params = {}) =>
    client.get("/cms/comments/", { params }),

  // GET    /api/cms/comments/:id/
  detail: (id) =>
    client.get(`/cms/comments/${id}/`),

  // POST   /api/cms/comments/
  // body: { comment, content_type, object_id, parent, rating }
  create: (data) =>
    client.post("/cms/comments/", data),

  // PATCH  /api/cms/comments/:id/
  update: (id, data) =>
    client.patch(`/cms/comments/${id}/`, data),

  // DELETE /api/cms/comments/:id/  (soft delete)
  delete: (id) =>
    client.delete(`/cms/comments/${id}/`),

  // GET    /api/cms/comments/?is_approved=false
  // triggers: CommentManager.pending()
  pending: (params = {}) =>
    client.get("/cms/comments/", { params: { ...params, is_approved: false } }),

  // POST   /api/cms/comments/:id/approve/
  // triggers: approve() backend method
  approve: (id) =>
    client.post(`/cms/comments/${id}/approve/`),

  // POST   /api/cms/comments/:id/flag/
  // triggers: flag() backend method
  // body: { reason }
  flag: (id, reason) =>
    client.post(`/cms/comments/${id}/flag/`, { reason }),

  // POST   /api/cms/comments/:id/like/
  // triggers: increment_like_count()
  like: (id) =>
    client.post(`/cms/comments/${id}/like/`),

  // GET    /api/cms/comments/:id/replies/
  // triggers: get_replies()
  replies: (id) =>
    client.get(`/cms/comments/${id}/replies/`),
};

// ─────────────────────────────────────────────────────────────────
//  SiteAnalytics Model → /api/cms/analytics/
// ─────────────────────────────────────────────────────────────────
export const siteAnalyticsAPI = {
  // GET    /api/cms/analytics/
  // params: { date_from, date_to, page }
  list: (params = {}) =>
    client.get("/cms/analytics/", { params }),

  // GET    /api/cms/analytics/today/
  // triggers: get_daily_stats() classmethod
  today: () =>
    client.get("/cms/analytics/today/"),

  // GET    /api/cms/analytics/range/
  // triggers: get_date_range_stats() classmethod
  // params: { start_date, end_date }
  range: (start_date, end_date) =>
    client.get("/cms/analytics/range/", { params: { start_date, end_date } }),
};

// ─────────────────────────────────────────────────────────────────
//  ContentPermission Model → /api/cms/permissions/
// ─────────────────────────────────────────────────────────────────
export const contentPermissionAPI = {
  // GET    /api/cms/permissions/
  // params: { content, permission_type, target_id, is_active, page }
  list: (params = {}) =>
    client.get("/cms/permissions/", { params }),

  // GET    /api/cms/permissions/:id/
  detail: (id) =>
    client.get(`/cms/permissions/${id}/`),

  // POST   /api/cms/permissions/
  // body: { content, permission_type, target_id, permissions, expires_at }
  create: (data) =>
    client.post("/cms/permissions/", data),

  // PATCH  /api/cms/permissions/:id/
  update: (id, data) =>
    client.patch(`/cms/permissions/${id}/`, data),

  // DELETE /api/cms/permissions/:id/
  delete: (id) =>
    client.delete(`/cms/permissions/${id}/`),

  // POST   /api/cms/permissions/check/
  // triggers: check_permission() classmethod (multi-level caching)
  // body: { content_id, user_id, perm_type }
  check: (content_id, perm_type) =>
    client.post("/cms/permissions/check/", { content_id, perm_type }),
};

// ─────────────────────────────────────────────────────────────────
//  BannerReward Model → /api/cms/banner-rewards/
// ─────────────────────────────────────────────────────────────────
export const bannerRewardAPI = {
  // GET    /api/cms/banner-rewards/
  // params: { banner, user, is_processed, reward_type, page }
  list: (params = {}) =>
    client.get("/cms/banner-rewards/", { params }),

  // GET    /api/cms/banner-rewards/:id/
  detail: (id) =>
    client.get(`/cms/banner-rewards/${id}/`),

  // GET    /api/cms/banner-rewards/stats/
  stats: () =>
    client.get("/cms/banner-rewards/stats/"),
};

// ─────────────────────────────────────────────────────────────────
//  PermissionAuditLog Model → /api/cms/permission-audit/
// ─────────────────────────────────────────────────────────────────
export const permissionAuditAPI = {
  // GET    /api/cms/permission-audit/
  // params: { action, user_id, content_id, permission_id, page }
  list: (params = {}) =>
    client.get("/cms/permission-audit/", { params }),

  // GET    /api/cms/permission-audit/:id/
  detail: (id) =>
    client.get(`/cms/permission-audit/${id}/`),
};

// ─────────────────────────────────────────────────────────────────
//  Tracking logs (read-only analytics)
// ─────────────────────────────────────────────────────────────────

// BannerImpression → /api/cms/banner-impressions/
export const bannerImpressionAPI = {
  list: (params = {}) =>
    client.get("/cms/banner-impressions/", { params }),
};

// BannerClick → /api/cms/banner-clicks/
export const bannerClickAPI = {
  list: (params = {}) =>
    client.get("/cms/banner-clicks/", { params }),
};

// FAQFeedback → /api/cms/faq-feedback/
export const faqFeedbackAPI = {
  list: (params = {}) =>
    client.get("/cms/faq-feedback/", { params }),
};

// ContentViewLog → /api/cms/content-view-logs/
export const contentViewLogAPI = {
  list: (params = {}) =>
    client.get("/cms/content-view-logs/", { params }),
};

// ContentShare → /api/cms/content-shares/
export const contentShareAPI = {
  list: (params = {}) =>
    client.get("/cms/content-shares/", { params }),
};