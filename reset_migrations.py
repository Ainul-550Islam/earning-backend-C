from django.db import connection
c = connection.cursor()

# Delete old migration records
c.execute("DELETE FROM django_migrations WHERE app='alerts'")
print("Deleted migration records")

connection.commit()
print("Done! Now run: python manage.py migrate alerts")