# AD NETWORKS — EXTENSION GUIDE
## "এক কাজের জন্য একটাই মালিক"
### নতুন Feature যোগ করার সম্পূর্ণ গাইড

---

## ✅ মূল নীতি

> **Core files কখনো touch করবেন না।**
> নতুন feature = নতুন file।
> Core code = read-only।

---

## 📁 Extension File Structure

```
api/ad_networks/
├── extensions/                    ← সব নতুন feature এখানে
│   ├── __init__.py
│   ├── new_feature/
│   │   ├── __init__.py
│   │   ├── models.py              ← নতুন model
│   │   ├── serializers.py         ← নতুন serializer
│   │   ├── views.py               ← নতুন views
│   │   ├── urls.py                ← নতুন URLs
│   │   ├── admin.py               ← নতুন admin
│   │   ├── signals.py             ← নতুন signals
│   │   ├── tasks.py               ← নতুন Celery tasks
│   │   └── tests.py               ← নতুন tests
```

---

## 🔧 Step-by-Step: নতুন Feature যোগ করা

### Step 1 — Extension Folder তৈরি করুন

```bash
mkdir -p api/ad_networks/extensions/your_feature
touch api/ad_networks/extensions/__init__.py
touch api/ad_networks/extensions/your_feature/__init__.py
```

---

### Step 2 — নতুন Model তৈরি করুন

```python
# api/ad_networks/extensions/your_feature/models.py

from django.db import models
from api.ad_networks.abstracts import TenantModel, TimestampedModel
from api.ad_networks.models import Offer, AdNetwork  # core থেকে import


class YourNewModel(TenantModel, TimestampedModel):
    """
    নতুন feature এর model।
    Core model touch না করে ForeignKey দিয়ে connect করুন।
    """
    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        related_name='your_feature_items'  # unique related_name দিন
    )
    network = models.ForeignKey(
        AdNetwork,
        on_delete=models.CASCADE,
        related_name='your_feature_networks'
    )
    
    # আপনার নতুন fields
    your_field = models.CharField(max_length=255)
    your_data = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'ad_networks_ext_your_feature'  # prefix: ad_networks_ext_
        verbose_name = 'Your Feature'
        verbose_name_plural = 'Your Features'
    
    def __str__(self):
        return f"{self.offer} - {self.your_field}"
```

---

### Step 3 — Migration তৈরি করুন

```bash
# extension app কে INSTALLED_APPS এ add করুন
# config/settings/base.py তে:
# 'api.ad_networks.extensions.your_feature',

python manage.py makemigrations your_feature
python manage.py migrate your_feature
```

---

### Step 4 — Serializer তৈরি করুন

```python
# api/ad_networks/extensions/your_feature/serializers.py

from rest_framework import serializers
from .models import YourNewModel
from api.ad_networks.serializers import OfferSerializer  # core serializer reuse


class YourNewModelSerializer(serializers.ModelSerializer):
    offer_detail = OfferSerializer(source='offer', read_only=True)
    
    class Meta:
        model = YourNewModel
        fields = '__all__'
        read_only_fields = ['tenant_id', 'created_at', 'updated_at']
```

---

### Step 5 — Views তৈরি করুন

```python
# api/ad_networks/extensions/your_feature/views.py

from rest_framework import viewsets, permissions
from api.ad_networks.mixins import TenantMixin  # core mixin reuse
from .models import YourNewModel
from .serializers import YourNewModelSerializer


class YourNewModelViewSet(TenantMixin, viewsets.ModelViewSet):
    """নতুন feature এর ViewSet"""
    serializer_class = YourNewModelSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return YourNewModel.objects.filter(
            tenant_id=getattr(self.request, 'tenant_id', 'default')
        ).select_related('offer', 'network')
    
    def perform_create(self, serializer):
        serializer.save(
            tenant_id=getattr(self.request, 'tenant_id', 'default')
        )
```

---

### Step 6 — URLs তৈরি করুন

```python
# api/ad_networks/extensions/your_feature/urls.py

from rest_framework.routers import DefaultRouter
from .views import YourNewModelViewSet

router = DefaultRouter()
router.register(r'your-feature', YourNewModelViewSet, basename='your-feature')

urlpatterns = router.urls
```

```python
# api/ad_networks/urls.py তে add করুন (শুধু এই একটা লাইন):
path('extensions/', include('api.ad_networks.extensions.your_feature.urls')),
```

---

### Step 7 — Admin তৈরি করুন

```python
# api/ad_networks/extensions/your_feature/admin.py

from django.contrib import admin
from .models import YourNewModel


@admin.register(YourNewModel)
class YourNewModelAdmin(admin.ModelAdmin):
    list_display = ['offer', 'network', 'your_field', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['offer__title', 'your_field']
    
    class Media:
        css = {'all': ('admin/css/ad_networks_admin.css',)}
```

---

### Step 8 — Signals (Optional)

```python
# api/ad_networks/extensions/your_feature/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import YourNewModel


@receiver(post_save, sender=YourNewModel)
def on_your_feature_created(sender, instance, created, **kwargs):
    if created:
        # আপনার logic
        pass
```

```python
# api/ad_networks/extensions/your_feature/apps.py

from django.apps import AppConfig


class YourFeatureConfig(AppConfig):
    name = 'api.ad_networks.extensions.your_feature'
    
    def ready(self):
        import api.ad_networks.extensions.your_feature.signals  # noqa
```

---

### Step 9 — Tasks (Optional)

```python
# api/ad_networks/extensions/your_feature/tasks.py

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(name='ad_networks.extensions.your_feature.process')
def process_your_feature(item_id: int):
    """Background task for your feature"""
    from .models import YourNewModel
    try:
        item = YourNewModel.objects.get(id=item_id)
        # আপনার processing logic
        logger.info(f"Processed: {item}")
    except YourNewModel.DoesNotExist:
        logger.error(f"Item {item_id} not found")
```

---

## 🚫 যা কখনো করবেন না

```python
# ❌ WRONG — core file modify করা
# api/ad_networks/models.py তে নতুন field add করা
class Offer(models.Model):
    your_new_field = models.CharField(...)  # ← কখনো না!

# ❌ WRONG — core views modify করা  
# api/ad_networks/views.py তে নতুন logic add করা

# ❌ WRONG — core admin modify করা
# api/ad_networks/admin.py তে নতুন admin class add করা
```

```python
# ✅ CORRECT — extension তৈরি করুন
# api/ad_networks/extensions/your_feature/models.py তে
class YourFeature(models.Model):
    offer = models.ForeignKey(Offer, ...)  # core model reference করুন
    your_new_field = models.CharField(...)  # ← এভাবে!
```

---

## 📋 Quick Checklist

নতুন feature যোগ করার আগে:

- [ ] `extensions/your_feature/` folder তৈরি করেছি
- [ ] `models.py` এ `TenantModel` inherit করেছি
- [ ] `db_table` এ `ad_networks_ext_` prefix দিয়েছি
- [ ] `related_name` unique দিয়েছি
- [ ] `makemigrations` করেছি
- [ ] Core files touch করিনি
- [ ] Tests লিখেছি

---

## 🔄 Existing Feature Extend করতে চাইলে

```python
# Core model এর method override করতে চাইলে:
# Monkey patching ব্যবহার করুন — extension এর __init__.py তে

from api.ad_networks.models import Offer

def my_custom_method(self):
    return f"Custom: {self.title}"

# Attach করুন
Offer.my_custom_method = my_custom_method
```

---

## 📌 DB Table Naming Convention

| Type | Prefix | Example |
|------|--------|---------|
| Core tables | `ad_networks_` | `ad_networks_offer` |
| Extension tables | `ad_networks_ext_` | `ad_networks_ext_analytics` |
| Temp/cache tables | `ad_networks_tmp_` | `ad_networks_tmp_sync` |

---

## 🏆 Best Practices

1. **এক feature = এক folder** — মিশিয়ে রাখবেন না
2. **Core import করুন, modify করবেন না**
3. **DB table নাম সবসময় `ad_networks_ext_` prefix দিন**
4. **related_name সবসময় unique দিন**
5. **প্রতিটা extension এর নিজস্ব migration থাকবে**
6. **Tests লেখা mandatory**

---

*এই guide অনুসরণ করলে core ad_networks system কখনো break হবে না।*
*"এক কাজের জন্য একটাই মালিক।"*
