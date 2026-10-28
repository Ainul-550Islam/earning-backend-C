# Migration Chain — Important Notes

## Background
This project has TWO sets of migrations merged:

### Old production migrations (already applied in DB):
- 0001_initial → 0002 → 0003 → 0004
- 0005_rename_cms_banner... (index renames)
- 0006_rename_idx_priority... (index renames)

### New feature migrations (to be applied):
- 0005_new_cms_models (depends on old 0006!)
- 0006_extras_models → 0007_cpalead_core → ... → 0014_*

## How to migrate

### Fresh install (empty DB):
```bash
python manage.py migrate
```

### Existing DB (old code 0001-0006 already applied):
```bash
# Fake-apply old 0005/0006 so Django sees them as done (already in DB)
python manage.py migrate cms 0006_rename_idx_priority_start_date_end_date_904_idx_priority_start_date_en_32e_and_more --fake
# Now run new migrations normally
python manage.py migrate cms
```

### From a truly fresh DB (never had old code):
```bash
# Fake old 0005 and 0006 (index renames on tables created by 0001-0004)
python manage.py migrate cms 0006_rename_idx_priority_start_date_end_date_904_idx_priority_start_date_en_32e_and_more --fake
python manage.py migrate cms
```
