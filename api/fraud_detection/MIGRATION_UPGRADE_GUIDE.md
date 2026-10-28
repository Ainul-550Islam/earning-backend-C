# Migration Upgrade Guide
## পুরনো DB থেকে নতুন কোডে Migrate করার পদ্ধতি

### তোমার DB-র বর্তমান অবস্থা
পুরনো কোডে migration 0001–0006 applied আছে।  
নতুন কোডে migration 0001–0010 আছে।

---

### ⚠️ সমস্যাটা কি?

পুরনো `0004` ও `0005` migration ছিল empty (কোনো operation ছিল না)।  
নতুন `0004` ও `0005` তে `RenameIndex` operations আছে।

Django migration system filename দিয়ে track করে — তাই পুরনো DB মনে করছে  
`0004` ও `0005` already applied, কিন্তু আসলে নতুন RenameIndex গুলো চলেনি।

তবে **সমস্যা নেই** — কারণ পুরনো `0006` (AddIndex) সরাসরি `idx_*` নামে  
indexes তৈরি করেছিল। DB-তে ঠিক নামের indexes আছে, শুধু migration history আলাদা।

---

### ✅ Upgrade Steps (Existing DB)

```bash
# Step 1: নতুন কোড deploy করো (পুরনো DB touch করো না এখনো)

# Step 2: নতুন 0006, 0007, 0008, 0009, 0010 run করো
python manage.py migrate fraud_detection

# যদি error আসে "index already exists" তাহলে Step 3 করো:

# Step 3: Fake migrate করো শুধু নতুন migrations এর জন্য
python manage.py migrate fraud_detection 0010 --fake

# Step 4: Verify
python manage.py showmigrations fraud_detection
```

---

### ✅ Fresh Install Steps

```bash
python manage.py migrate
# সব migrations 0001–0010 ক্রমানুসারে চলবে, কোনো সমস্যা নেই।
```

---

### নতুন Models (migration 0009 যোগ করেছে)

- `FraudCase` — fraud case management
- `FraudCaseEvidence` — evidence tracking
- `FraudCaseAction` — case actions/workflow
- `FraudWhitelist` — whitelist management
- `FraudNotification` — notification system
- `integrity_hash` + `previous_hash` fields on existing models

---

### Rollback করতে হলে

```bash
python manage.py migrate fraud_detection 0005
```
