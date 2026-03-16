from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# ১. শুধুমাত্র ViewSet গুলো এখানে থাকবে
router.register(r'languages', views.LanguageViewSet, basename='language')
router.register(r'translation-keys', views.TranslationKeyViewSet, basename='translation-key')
router.register(r'translations', views.TranslationViewSet, basename='translation')
router.register(r'missing-translations', views.MissingTranslationViewSet, basename='missing-translation')
router.register(r'translation-cache', views.TranslationCacheViewSet, basename='translation-cache')

# --- ভুল ছিল এখানে: 'user-preferences' রাউটার থেকে সরিয়ে দিন ---

urlpatterns = [
    # রাউটারের ইউআরএল
    path('', include(router.urls)),
    
    # ২. 'user-preferences' এখন এখানে আলাদাভাবে বসবে
    path('user-preferences/', views.UserLanguagePreferenceView.as_view(), name='user-preference'),
    
    # বাকি আগের সব ইউআরএল এখানে থাকবে...
    path('public/translations/<str:language_code>/', 
         views.get_translations, name='public-translations'),
    path('report-missing/', 
         views.report_missing_translation, name='report-missing-translation'),
    path('tools/detect-language/', 
         views.TranslationToolsView.as_view(), name='detect-language'),
    path('tools/translate/', 
         views.TranslationToolsView.as_view(), name='translate-text'),
    path('status/', 
         views.LocalizationStatusView.as_view(), name='localization-status'),
    path('translations/export/', 
         views.TranslationViewSet.as_view({'post': 'export'}), name='export-translations'),
    path('translations/import/', 
         views.TranslationViewSet.as_view({'post': 'import_translations'}), name='import-translations'),
]