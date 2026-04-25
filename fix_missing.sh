#!/bin/bash
echo "Fixing missing DB tables and columns..."
python manage.py shell < /tmp/fix_db3.py
python manage.py shell < /tmp/fix_db.py
python manage.py shell -c "
from django.db import connection
from django.apps import apps
with connection.cursor() as cursor:
    for model in apps.get_models():
        table = model._meta.db_table
        cursor.execute('SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)', [table])
        if not cursor.fetchone()[0]:
            print('Still missing: ' + table)
print('Check complete!')
"
echo "Done!"
