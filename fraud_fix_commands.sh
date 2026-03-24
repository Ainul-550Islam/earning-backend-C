cp api/fraud_detection/models.py api/fraud_detection/models.py.bak
cp api/fraud_detection/views.py api/fraud_detection/views.py.bak
cp api/fraud_detection/signals.py api/fraud_detection/signals.py.bak
echo "[OK] Backup done"

python -c "
with open('api/fraud_detection/models.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace(
    'device_id = models.CharField(max_length=255, unique=True)',
    'device_id = models.CharField(max_length=255, unique=True, null=True, blank=True, default=None)'
)
with open('api/fraud_detection/models.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('[OK] models.py fixed')
"

python -c "
import re
with open('api/fraud_detection/models.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = re.sub(r'(class Meta:.*?)([ \t]+ordering = \[.*?\]\n)(.*?)([ \t]+ordering = \[.*?\]\n)', r'\1\3\4', c, flags=re.DOTALL)
with open('api/fraud_detection/models.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('[OK] Duplicate ordering removed')
"

python -c "
with open('api/fraud_detection/views.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace(
    \"device_id=device_data.get('device_id', 'unknown'),\",
    \"device_id=device_data.get('device_id') or str(__import__('uuid').uuid4()),\"
)
c = c.replace(
    'DeviceFingerprint.objects.create(',
    'DeviceFingerprint.objects.get_or_create('
)
with open('api/fraud_detection/views.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('[OK] views.py fixed')
"

python -c "
with open('api/fraud_detection/signals.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace(
    'instance.trust_score = max(0, instance.trust_score - 20)\n                instance.save()',
    'DeviceFingerprint.objects.filter(pk=instance.pk).update(trust_score=max(0, instance.trust_score - 20))'
)
with open('api/fraud_detection/signals.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('[OK] signals.py fixed')
"

python manage.py shell -c "
from api.fraud_detection.models import DeviceFingerprint
deleted = DeviceFingerprint.objects.filter(device_id='').delete()
print('Deleted empty:', deleted)
"

python manage.py makemigrations fraud_detection --name fix_device_fingerprint_null
python manage.py migrate fraud_detection

git add api/fraud_detection/models.py api/fraud_detection/views.py api/fraud_detection/signals.py api/fraud_detection/migrations/
git commit -m "fix: DeviceFingerprint unique constraint crash fix"
echo ""
echo "===== ALL DONE! Deploy to Railway ====="
