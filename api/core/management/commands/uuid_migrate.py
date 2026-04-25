from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Migrate tenants.id from bigint to UUID'

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            self.stdout.write("Step 1: Add uuid column to tenants...")
            cursor.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS new_id UUID DEFAULT gen_random_uuid()")
            cursor.execute("UPDATE tenants SET new_id = gen_random_uuid() WHERE new_id IS NULL")
            self.stdout.write("Done!")

            self.stdout.write("Step 2: Get all FK tables...")
            cursor.execute("""
                SELECT tc.table_name, kcu.column_name, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.referential_constraints rc ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.key_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND ccu.table_name = 'tenants'
                AND ccu.column_name = 'id'
            """)
            fk_tables = cursor.fetchall()
            self.stdout.write("Found " + str(len(fk_tables)) + " FK references")

            self.stdout.write("Step 3: Add new UUID columns...")
            for row in fk_tables:
                table_name, col_name, constraint_name = row
                try:
                    cursor.execute("ALTER TABLE " + table_name + " ADD COLUMN IF NOT EXISTS new_" + col_name + " UUID")
                    self.stdout.write("Added: " + table_name + ".new_" + col_name)
                except Exception as e:
                    self.stdout.write("SKIP: " + table_name + " - " + str(e)[:60])

            self.stdout.write("Step 4: Update UUID values...")
            for row in fk_tables:
                table_name, col_name, constraint_name = row
                try:
                    sql = "UPDATE " + table_name + " t SET new_" + col_name + " = ten.new_id FROM tenants ten WHERE t." + col_name + " = ten.id"
                    cursor.execute(sql)
                    self.stdout.write("Updated: " + table_name)
                except Exception as e:
                    self.stdout.write("SKIP update: " + table_name + " - " + str(e)[:60])

        self.stdout.write("Phase 1 COMPLETE!")
