# Engagement Migration Guide
## পুরনো DB থেকে নতুন কোডে সুইচ করার ধাপ

### Step 1: Backup নাও
```bash
pg_dump -Fc your_db > backup_before_engagement_upgrade.dump
```

### Step 2: পুরনো engagement folder replace করো
```bash
# Project-এর engagement folder replace করো নতুন fixed_engagement দিয়ে
# (folder name engagement রাখো, fixed_engagement না)
```

### Step 3: পুরনো migrations fake করো
পুরনো 3টা migration already run হয়েছে DB-তে।
নতুন migration history তাদের জানে না — তাই fake করতে হবে।

```bash
python manage.py migrate engagement 0000_test_user --fake
```

### Step 4: নতুন migrations চালাও
```bash
python manage.py migrate engagement
```

এই command গুলো করবে:
- 0001: পুরনো tables patch (new columns add, old columns drop)
- 0002: Advanced systems (BattlePass, Guild, Social, ইত্যাদি)
- 0003: Compatibility fixes
- 0004: Constraint fixes
- 0005: Missing models

### Step 5: Check করো
```bash
python manage.py check
python manage.py showmigrations engagement
```

### যদি কোনো error হয়
```bash
# Rollback করো
pg_restore -d your_db backup_before_engagement_upgrade.dump
```
