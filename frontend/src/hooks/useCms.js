/**
 * useCms.js — CMS API hooks for EarnNexus Admin
 * Endpoint prefix: /api/cms/
 */
import { useState, useEffect, useCallback } from "react";
import client from "../api/client";


// ─── Generic paginated list helper ────────────────────────────────
const extractList = (data) => {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  if (data?.data) return data.data;
  return [];
};

// ══════════════════════════════════════════════════════════════════
//  useContentCategories
// ══════════════════════════════════════════════════════════════════
export function useContentCategories(params = {}) {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async (p = params) => {
    setLoading(true);
    try {
      const r = await client.get("cms/drf/categories/", { params: { page_size: 50, ...p } });
      setCategories(extractList(r.data));
    } catch (e) { setError(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, []);

  const create = async (data) => {
    const r = await client.post("cms/drf/categories/", data);
    setCategories((prev) => [r.data, ...prev]);
    return r.data;
  };

  const update = async (id, data) => {
    const r = await client.patch(`cms/drf/categories/${id}/`, data);
    setCategories((prev) => prev.map((c) => (c.id === id ? r.data : c)));
    return r.data;
  };

  const remove = async (id) => {
    await client.delete(`cms/drf/categories/${id}/`);
    setCategories((prev) => prev.filter((c) => c.id !== id));
  };

  return { categories, loading, error, fetch, create, update, remove };
}

// ══════════════════════════════════════════════════════════════════
//  useContentPages
// ══════════════════════════════════════════════════════════════════
export function useContentPages(params = {}) {
  const [pages, setPages] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async (p = params) => {
    setLoading(true);
    try {
      const r = await client.get("cms/drf/pages/", { params: { page_size: 50, ...p } });
      setPages(extractList(r.data));
    } catch (e) { /* silent */ }
    finally { setLoading(false); }
  }, []);

  const fetchStats = async () => {
    try {
      const r = await client.get("cms/drf/pages/stats/");
      setStats(r.data);
      return r.data;
    } catch { return null; }
  };

  const fetchPublished = () => fetch({ status: "published" });
  const fetchFeatured  = () => fetch({ is_featured: true });

  useEffect(() => { fetch(); fetchStats(); }, []);

  const create = async (data) => {
    const r = await client.post("cms/drf/pages/", data);
    setPages((prev) => [r.data, ...prev]);
    return r.data;
  };

  const update = async (id, data) => {
    const r = await client.patch(`cms/drf/pages/${id}/`, data);
    setPages((prev) => prev.map((p) => (p.id === id ? r.data : p)));
    return r.data;
  };

  const remove = async (id) => {
    await client.delete(`cms/drf/pages/${id}/`);
    setPages((prev) => prev.filter((p) => p.id !== id));
  };

  return { pages, stats, loading, fetch, fetchPublished, fetchFeatured, fetchStats, create, update, remove };
}

// ══════════════════════════════════════════════════════════════════
//  useBanners
// ══════════════════════════════════════════════════════════════════
export function useBanners(params = {}) {
  const [banners, setBanners] = useState([]);
  const [stats, setStats]     = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async (p = params) => {
    setLoading(true);
    try {
      const [bRes, sRes] = await Promise.allSettled([
        client.get("cms/drf/banners/", { params: { page_size: 50, ...p } }),
        client.get("cms/drf/banners/stats/"),
      ]);
      if (bRes.status === "fulfilled") setBanners(extractList(bRes.value.data));
      if (sRes.status === "fulfilled") setStats(sRes.value.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, []);

  const create = async (data) => {
    const r = await client.post("cms/drf/banners/", data);
    setBanners((prev) => [r.data, ...prev]);
    return r.data;
  };

  const update = async (id, data) => {
    const r = await client.patch(`cms/drf/banners/${id}/`, data);
    setBanners((prev) => prev.map((b) => (b.id === id ? r.data : b)));
    return r.data;
  };

  const remove = async (id) => {
    await client.delete(`cms/drf/banners/${id}/`);
    setBanners((prev) => prev.filter((b) => b.id !== id));
  };

  const toggle = async (id, current) => update(id, { is_active: !current });

  return { banners, stats, loading, fetch, create, update, remove, toggle };
}

// ══════════════════════════════════════════════════════════════════
//  useFAQs
// ══════════════════════════════════════════════════════════════════
export function useFAQs(params = {}) {
  const [faqs, setFaqs]             = useState([]);
  const [faqCategories, setFaqCats] = useState([]);
  const [loading, setLoading]       = useState(true);

  const fetch = useCallback(async (p = params) => {
    setLoading(true);
    try {
      const [fRes, cRes] = await Promise.allSettled([
        client.get("cms/drf/faqs/", { params: { page_size: 50, ...p } }),
        client.get("cms/drf/faq-categories/", { params: { page_size: 50 } }),
      ]);
      if (fRes.status === "fulfilled") setFaqs(extractList(fRes.value.data));
      if (cRes.status === "fulfilled") setFaqCats(extractList(cRes.value.data));
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, []);

  const search = (q) => fetch({ q });

  const create = async (data) => {
    const r = await client.post("cms/drf/faqs/", data);
    setFaqs((prev) => [r.data, ...prev]);
    return r.data;
  };

  const update = async (id, data) => {
    const r = await client.patch(`cms/drf/faqs/${id}/`, data);
    setFaqs((prev) => prev.map((f) => (f.id === id ? r.data : f)));
    return r.data;
  };

  const remove = async (id) => {
    await client.delete(`cms/drf/faqs/${id}/`);
    setFaqs((prev) => prev.filter((f) => f.id !== id));
  };

  const createCategory = async (data) => {
    const r = await client.post("cms/drf/faq-categories/", data);
    setFaqCats((prev) => [r.data, ...prev]);
    return r.data;
  };

  return { faqs, faqCategories, loading, fetch, search, create, update, remove, createCategory };
}

// ══════════════════════════════════════════════════════════════════
//  useComments
// ══════════════════════════════════════════════════════════════════
export function useComments(params = {}) {
  const [comments, setComments] = useState([]);
  const [loading, setLoading]   = useState(true);

  const fetch = useCallback(async (p = params) => {
    setLoading(true);
    try {
      const r = await client.get("cms/drf/comments/", { params: { page_size: 50, ...p } });
      setComments(extractList(r.data));
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  const fetchPending = () => fetch({ is_approved: "false" });

  useEffect(() => { fetch(); }, []);

  const approve = async (id) => {
    await client.post(`cms/drf/comments/${id}/approve/`);
    setComments((prev) => prev.map((c) => (c.id === id ? { ...c, is_approved: true } : c)));
  };

  const flag = async (id, reason = "spam") => {
    await client.post(`cms/drf/comments/${id}/flag/`, { flag_reason: reason });
    setComments((prev) => prev.map((c) => (c.id === id ? { ...c, is_flagged: true } : c)));
  };

  const remove = async (id) => {
    await client.delete(`cms/drf/comments/${id}/`);
    setComments((prev) => prev.filter((c) => c.id !== id));
  };

  return { comments, loading, fetch, fetchPending, approve, flag, remove };
}

// ══════════════════════════════════════════════════════════════════
//  useSiteAnalytics
// ══════════════════════════════════════════════════════════════════
export function useSiteAnalytics() {
  const [analytics, setAnalytics] = useState([]);
  const [today, setToday]         = useState(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [aRes, tRes] = await Promise.allSettled([
          client.get("cms/drf/analytics/", { params: { page_size: 30 } }),
          client.get("cms/drf/analytics/today/"),
        ]);
        if (aRes.status === "fulfilled") setAnalytics(extractList(aRes.value.data));
        if (tRes.status === "fulfilled") setToday(tRes.value.data);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const fetchRange = async (startDate, endDate) => {
    try {
      const r = await client.get("cms/drf/analytics/", { params: { start_date: startDate, end_date: endDate, page_size: 30 } });
      setAnalytics(extractList(r.data));
    } catch { /* silent */ }
  };

  return { analytics, today, loading, fetchRange };
}

// ══════════════════════════════════════════════════════════════════
//  useFiles
// ══════════════════════════════════════════════════════════════════
export function useFiles(params = {}) {
  const [files, setFiles]     = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const r = await client.get("cms/drf/files/", { params: { page_size: 50, ...params } });
        setFiles(extractList(r.data));
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const upload = async (formData) => {
    const r = await client.post("cms/drf/files/", formData, { headers: { "Content-Type": "multipart/form-data" } });
    setFiles((prev) => [r.data, ...prev]);
    return r.data;
  };

  const remove = async (id) => {
    await client.delete(`cms/drf/files/${id}/`);
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const download = async (id) => {
    const file = files.find((f) => f.id === id);
    if (file?.file) window.open(file.file, "_blank");
  };

  return { files, loading, upload, remove, download };
}

// ══════════════════════════════════════════════════════════════════
//  useGalleries
// ══════════════════════════════════════════════════════════════════
export function useGalleries() {
  const [galleries, setGalleries] = useState([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const r = await client.get("cms/drf/galleries/", { params: { page_size: 30 } });
        setGalleries(extractList(r.data));
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const create = async (data) => {
    const r = await client.post("cms/drf/galleries/", data);
    setGalleries((prev) => [r.data, ...prev]);
    return r.data;
  };

  const remove = async (id) => {
    await client.delete(`cms/drf/galleries/${id}/`);
    setGalleries((prev) => prev.filter((g) => g.id !== id));
  };

  return { galleries, loading, create, remove };
}



// import { useState, useEffect, useCallback } from "react";
// import {
//   contentCategoryAPI,
//   contentPageAPI,
//   bannerAPI,
//   faqCategoryAPI,
//   faqAPI,
//   siteSettingsAPI,
//   imageGalleryAPI,
//   galleryImageAPI,
//   fileManagerAPI,
//   commentAPI,
//   siteAnalyticsAPI,
//   contentPermissionAPI,
//   bannerRewardAPI,
//   permissionAuditAPI,
// } from "../api/endpoints/cms";

// // ─────────────────────────────────────────────────────────────────
// //  useContentCategories → ContentCategory model
// // ─────────────────────────────────────────────────────────────────
// export const useContentCategories = (initialFilters = {}) => {
//   const [categories, setCategories] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchCategories = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await contentCategoryAPI.list(filters);
//       setCategories(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load categories");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createCategory = async (formData) => {
//     try {
//       const { data } = await contentCategoryAPI.create(formData);
//       setCategories((prev) => [...prev, data]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateCategory = async (id, formData) => {
//     try {
//       const { data } = await contentCategoryAPI.update(id, formData);
//       setCategories((prev) => prev.map((c) => (c.id === id ? data : c)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deleteCategory = async (id) => {
//     try {
//       await contentCategoryAPI.delete(id);
//       setCategories((prev) => prev.filter((c) => c.id !== id));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers get_breadcrumbs() with caching
//   const getBreadcrumbs = async (id) => {
//     try {
//       const { data } = await contentCategoryAPI.breadcrumbs(id);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchCategories(); }, [fetchCategories]);

//   return {
//     categories, loading, error, filters, setFilters,
//     createCategory, updateCategory, deleteCategory, getBreadcrumbs,
//     refetch: fetchCategories,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useContentPages → ContentPage model
// // ─────────────────────────────────────────────────────────────────
// export const useContentPages = (initialFilters = {}) => {
//   const [pages, setPages] = useState([]);
//   const [stats, setStats] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);
//   // filters: { status, page_type, category, is_featured, visibility, language }

//   const fetchPages = useCallback(async () => {
//     try {
//       setLoading(true);
//       const [pagesRes, statsRes] = await Promise.all([
//         contentPageAPI.list(filters),
//         contentPageAPI.stats(),
//       ]);
//       setPages(pagesRes.data?.results ?? pagesRes.data);
//       setStats(statsRes.data);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load pages");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createPage = async (formData) => {
//     try {
//       const { data } = await contentPageAPI.create(formData);
//       setPages((prev) => [data, ...prev]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updatePage = async (slug, formData) => {
//     try {
//       const { data } = await contentPageAPI.update(slug, formData);
//       setPages((prev) => prev.map((p) => (p.slug === slug ? data : p)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deletePage = async (slug) => {
//     try {
//       await contentPageAPI.delete(slug);
//       setPages((prev) => prev.filter((p) => p.slug !== slug));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // ContentPageManager methods
//   const fetchPublished = async () => {
//     try {
//       const { data } = await contentPageAPI.published();
//       setPages(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed");
//     }
//   };

//   const fetchFeatured = async () => {
//     try {
//       const { data } = await contentPageAPI.featured();
//       setPages(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed");
//     }
//   };

//   // triggers create_new_version() backend method
//   const createVersion = async (slug) => {
//     try {
//       const { data } = await contentPageAPI.createVersion(slug);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers bulk_increment_views() classmethod
//   const bulkIncrementViews = async (ids) => {
//     try {
//       await contentPageAPI.bulkIncrementViews(ids);
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchPages(); }, [fetchPages]);

//   return {
//     pages, stats, loading, error, filters, setFilters,
//     createPage, updatePage, deletePage,
//     fetchPublished, fetchFeatured,  // ContentPageManager
//     createVersion, bulkIncrementViews,
//     refetch: fetchPages,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useBanners → Banner model
// // ─────────────────────────────────────────────────────────────────
// export const useBanners = (initialFilters = {}) => {
//   const [banners, setBanners] = useState([]);
//   const [stats, setStats] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);
//   // filters: { banner_type, position, is_active, target_device }

//   const fetchBanners = useCallback(async () => {
//     try {
//       setLoading(true);
//       const [bannersRes, statsRes] = await Promise.all([
//         bannerAPI.list(filters),
//         bannerAPI.stats(),
//       ]);
//       setBanners(Array.isArray(bannersRes.data?.results) ? bannersRes.data.results : Array.isArray(bannersRes.data) ? bannersRes.data : Array.isArray(bannersRes) ? bannersRes : []);
//       setStats(statsRes.data);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load banners");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createBanner = async (formData) => {
//     try {
//       const { data } = await bannerAPI.create(formData);
//       setBanners((prev) => [data, ...prev]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateBanner = async (id, formData) => {
//     try {
//       const { data } = await bannerAPI.update(id, formData);
//       setBanners((prev) => prev.map((b) => (b.id === id ? data : b)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deleteBanner = async (id) => {
//     try {
//       await bannerAPI.delete(id);
//       setBanners((prev) => prev.filter((b) => b.id !== id));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers record_impression() → BannerImpression created
//   const recordImpression = async (id) => {
//     try {
//       await bannerAPI.recordImpression(id);
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers record_click() + award_reward()
//   const recordClick = async (id) => {
//     try {
//       const { data } = await bannerAPI.recordClick(id);
//       setBanners((prev) => prev.map((b) => (b.id === id ? data : b)));
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers get_for_position() / get_rotating_banners()
//   const fetchByPosition = async (position, device = "all", limit = 5) => {
//     try {
//       const { data } = await bannerAPI.byPosition(position, device, limit);
//       return { success: true, data: data?.results ?? data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchBanners(); }, [fetchBanners]);

//   return {
//     banners, stats, loading, error, filters, setFilters,
//     createBanner, updateBanner, deleteBanner,
//     recordImpression, recordClick, fetchByPosition,
//     refetch: fetchBanners,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useFAQCategories → FAQCategory model
// // ─────────────────────────────────────────────────────────────────
// export const useFAQCategories = (initialFilters = {}) => {
//   const [categories, setCategories] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchCategories = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await faqCategoryAPI.list(filters);
//       setCategories(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createCategory = async (formData) => {
//     try {
//       const { data } = await faqCategoryAPI.create(formData);
//       setCategories((prev) => [...prev, data]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateCategory = async (id, formData) => {
//     try {
//       const { data } = await faqCategoryAPI.update(id, formData);
//       setCategories((prev) => prev.map((c) => (c.id === id ? data : c)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deleteCategory = async (id) => {
//     try {
//       await faqCategoryAPI.delete(id);
//       setCategories((prev) => prev.filter((c) => c.id !== id));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchCategories(); }, [fetchCategories]);

//   return {
//     categories, loading, error, filters, setFilters,
//     createCategory, updateCategory, deleteCategory,
//     refetch: fetchCategories,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useFAQs → FAQ model
// // ─────────────────────────────────────────────────────────────────
// export const useFAQs = (initialFilters = {}) => {
//   const [faqs, setFaqs] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchFaqs = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await faqAPI.list(filters);
//       setFaqs(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load FAQs");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createFaq = async (formData) => {
//     try {
//       const { data } = await faqAPI.create(formData);
//       setFaqs((prev) => [data, ...prev]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateFaq = async (slug, formData) => {
//     try {
//       const { data } = await faqAPI.update(slug, formData);
//       setFaqs((prev) => prev.map((f) => (f.slug === slug ? data : f)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deleteFaq = async (slug) => {
//     try {
//       await faqAPI.delete(slug);
//       setFaqs((prev) => prev.filter((f) => f.slug !== slug));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // FAQManager.search() method
//   const search = async (query) => {
//     try {
//       const { data } = await faqAPI.search(query);
//       setFaqs(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Search failed");
//     }
//   };

//   // triggers record_feedback() backend method
//   const submitFeedback = async (slug, is_helpful, feedback_text = "") => {
//     try {
//       const { data } = await faqAPI.feedback(slug, is_helpful, feedback_text);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchFaqs(); }, [fetchFaqs]);

//   return {
//     faqs, loading, error, filters, setFilters,
//     createFaq, updateFaq, deleteFaq,
//     search, submitFeedback,  // FAQManager methods
//     refetch: fetchFaqs,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useSiteSettings → SiteSettings model
// // ─────────────────────────────────────────────────────────────────
// export const useSiteSettings = (initialFilters = {}) => {
//   const [settings, setSettings] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchSettings = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await siteSettingsAPI.list(filters);
//       setSettings(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load settings");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   // triggers set_setting() classmethod
//   const createSetting = async (formData) => {
//     try {
//       const { data } = await siteSettingsAPI.create(formData);
//       setSettings((prev) => [...prev, data]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateSetting = async (key, formData) => {
//     try {
//       const { data } = await siteSettingsAPI.update(key, formData);
//       setSettings((prev) => prev.map((s) => (s.key === key ? data : s)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deleteSetting = async (key) => {
//     try {
//       await siteSettingsAPI.delete(key);
//       setSettings((prev) => prev.filter((s) => s.key !== key));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchSettings(); }, [fetchSettings]);

//   return {
//     settings, loading, error, filters, setFilters,
//     createSetting, updateSetting, deleteSetting,
//     refetch: fetchSettings,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useComments → Comment model
// // ─────────────────────────────────────────────────────────────────
// export const useComments = (initialFilters = {}) => {
//   const [comments, setComments] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);
//   // filters: { content_type, object_id, is_approved, is_flagged, user }

//   const fetchComments = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await commentAPI.list(filters);
//       setComments(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load comments");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createComment = async (formData) => {
//     try {
//       const { data } = await commentAPI.create(formData);
//       setComments((prev) => [data, ...prev]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateComment = async (id, formData) => {
//     try {
//       const { data } = await commentAPI.update(id, formData);
//       setComments((prev) => prev.map((c) => (c.id === id ? data : c)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // soft delete (sets is_active=false)
//   const deleteComment = async (id) => {
//     try {
//       await commentAPI.delete(id);
//       setComments((prev) => prev.filter((c) => c.id !== id));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers approve() backend method
//   const approve = async (id) => {
//     try {
//       const { data } = await commentAPI.approve(id);
//       setComments((prev) => prev.map((c) => (c.id === id ? data : c)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers flag() backend method
//   const flag = async (id, reason) => {
//     try {
//       const { data } = await commentAPI.flag(id, reason);
//       setComments((prev) => prev.map((c) => (c.id === id ? data : c)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // CommentManager.pending()
//   const fetchPending = async () => {
//     try {
//       const { data } = await commentAPI.pending();
//       setComments(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed");
//     }
//   };

//   useEffect(() => { fetchComments(); }, [fetchComments]);

//   return {
//     comments, loading, error, filters, setFilters,
//     createComment, updateComment, deleteComment,
//     approve, flag,
//     fetchPending, // CommentManager.pending()
//     refetch: fetchComments,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useSiteAnalytics → SiteAnalytics model
// // ─────────────────────────────────────────────────────────────────
// export const useSiteAnalytics = (initialFilters = {}) => {
//   const [analytics, setAnalytics] = useState([]);
//   const [today, setToday] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchAnalytics = useCallback(async () => {
//     try {
//       setLoading(true);
//       const [listRes, todayRes] = await Promise.all([
//         siteAnalyticsAPI.list(filters),
//         siteAnalyticsAPI.today(),
//       ]);
//       setAnalytics(listRes.data?.results ?? listRes.data);
//       setToday(todayRes.data);
//       // today: triggers get_daily_stats() classmethod
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load analytics");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   // triggers get_date_range_stats() classmethod
//   const fetchRange = async (start_date, end_date) => {
//     try {
//       const { data } = await siteAnalyticsAPI.range(start_date, end_date);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

//   return {
//     analytics, today, loading, error, filters, setFilters,
//     fetchRange,
//     refetch: fetchAnalytics,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useContentPermissions → ContentPermission model
// // ─────────────────────────────────────────────────────────────────
// export const useContentPermissions = (initialFilters = {}) => {
//   const [permissions, setPermissions] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchPermissions = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await contentPermissionAPI.list(filters);
//       setPermissions(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load permissions");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createPermission = async (formData) => {
//     try {
//       const { data } = await contentPermissionAPI.create(formData);
//       setPermissions((prev) => [...prev, data]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updatePermission = async (id, formData) => {
//     try {
//       const { data } = await contentPermissionAPI.update(id, formData);
//       setPermissions((prev) => prev.map((p) => (p.id === id ? data : p)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deletePermission = async (id) => {
//     try {
//       await contentPermissionAPI.delete(id);
//       setPermissions((prev) => prev.filter((p) => p.id !== id));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers check_permission() classmethod (multi-level caching)
//   const checkPermission = async (content_id, perm_type) => {
//     try {
//       const { data } = await contentPermissionAPI.check(content_id, perm_type);
//       return { success: true, allowed: data.allowed };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchPermissions(); }, [fetchPermissions]);

//   return {
//     permissions, loading, error, filters, setFilters,
//     createPermission, updatePermission, deletePermission,
//     checkPermission, // check_permission() classmethod
//     refetch: fetchPermissions,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useBannerRewards → BannerReward model
// // ─────────────────────────────────────────────────────────────────
// export const useBannerRewards = (initialFilters = {}) => {
//   const [rewards, setRewards] = useState([]);
//   const [stats, setStats] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);
//   // filters: { banner, user, is_processed, reward_type }

//   const fetchRewards = useCallback(async () => {
//     try {
//       setLoading(true);
//       const [rewardsRes, statsRes] = await Promise.all([
//         bannerRewardAPI.list(filters),
//         bannerRewardAPI.stats(),
//       ]);
//       setRewards(rewardsRes.data?.results ?? rewardsRes.data);
//       setStats(statsRes.data);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load rewards");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   useEffect(() => { fetchRewards(); }, [fetchRewards]);

//   return { rewards, stats, loading, error, filters, setFilters, refetch: fetchRewards };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useImageGalleries → ImageGallery model
// // ─────────────────────────────────────────────────────────────────
// export const useImageGalleries = (initialFilters = {}) => {
//   const [galleries, setGalleries] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchGalleries = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await imageGalleryAPI.list(filters);
//       setGalleries(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load galleries");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const createGallery = async (formData) => {
//     try {
//       const { data } = await imageGalleryAPI.create(formData);
//       setGalleries((prev) => [data, ...prev]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateGallery = async (slug, formData) => {
//     try {
//       const { data } = await imageGalleryAPI.update(slug, formData);
//       setGalleries((prev) => prev.map((g) => (g.slug === slug ? data : g)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deleteGallery = async (slug) => {
//     try {
//       await imageGalleryAPI.delete(slug);
//       setGalleries((prev) => prev.filter((g) => g.slug !== slug));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchGalleries(); }, [fetchGalleries]);

//   return {
//     galleries, loading, error, filters, setFilters,
//     createGallery, updateGallery, deleteGallery,
//     refetch: fetchGalleries,
//   };
// };

// // ─────────────────────────────────────────────────────────────────
// //  useFiles → FileManager model
// // ─────────────────────────────────────────────────────────────────
// export const useFiles = (initialFilters = {}) => {
//   const [files, setFiles] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [filters, setFilters] = useState(initialFilters);

//   const fetchFiles = useCallback(async () => {
//     try {
//       setLoading(true);
//       const { data } = await fileManagerAPI.list(filters);
//       setFiles(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : []);
//     } catch (err) {
//       setError(err.response?.data?.detail || "Failed to load files");
//     } finally {
//       setLoading(false);
//     }
//   }, [filters]);

//   const uploadFile = async (formData) => {
//     try {
//       const { data } = await fileManagerAPI.create(formData);
//       setFiles((prev) => [data, ...prev]);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const updateFile = async (id, formData) => {
//     try {
//       const { data } = await fileManagerAPI.update(id, formData);
//       setFiles((prev) => prev.map((f) => (f.id === id ? data : f)));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   const deleteFile = async (id) => {
//     try {
//       await fileManagerAPI.delete(id);
//       setFiles((prev) => prev.filter((f) => f.id !== id));
//       return { success: true };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   // triggers increment_download_count()
//   const download = async (id) => {
//     try {
//       const { data } = await fileManagerAPI.download(id);
//       return { success: true, data };
//     } catch (err) {
//       return { success: false, error: err.response?.data };
//     }
//   };

//   useEffect(() => { fetchFiles(); }, [fetchFiles]);

//   return {
//     files, loading, error, filters, setFilters,
//     uploadFile, updateFile, deleteFile, download,
//     refetch: fetchFiles,
//   };
// };