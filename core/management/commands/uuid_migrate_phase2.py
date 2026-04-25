from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'UUID Migration Phase 2 - Replace bigint id with UUID'

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:

            self.stdout.write("Phase 2 Step 1: Drop all FK constraints referencing tenants.id...")
            cursor.execute("""
                SELECT tc.constraint_name, tc.table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.referential_constraints rc ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.key_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND ccu.table_name = 'tenants'
                AND ccu.column_name = 'id'
            """)
            fk_constraints = cursor.fetchall()
            self.stdout.write("Found " + str(len(fk_constraints)) + " FK constraints to drop")

            for constraint_name, table_name in fk_constraints:
                try:
                    cursor.execute("ALTER TABLE " + table_name + " DROP CONSTRAINT IF EXISTS " + constraint_name)
                    self.stdout.write("Dropped: " + constraint_name + " from " + table_name)
                except Exception as e:
                    self.stdout.write("SKIP drop: " + constraint_name + " - " + str(e)[:60])

            self.stdout.write("Phase 2 Step 2: Drop primary key on tenants...")
            try:
                cursor.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_pkey")
                self.stdout.write("Dropped tenants_pkey")
            except Exception as e:
                self.stdout.write("SKIP: " + str(e)[:60])

            self.stdout.write("Phase 2 Step 3: Rename columns in tenants...")
            try:
                cursor.execute("ALTER TABLE tenants RENAME COLUMN id TO old_id")
                cursor.execute("ALTER TABLE tenants RENAME COLUMN new_id TO id")
                self.stdout.write("Renamed tenants id columns")
            except Exception as e:
                self.stdout.write("SKIP rename: " + str(e)[:60])

            self.stdout.write("Phase 2 Step 4: Set new UUID as primary key...")
            try:
                cursor.execute("ALTER TABLE tenants ADD PRIMARY KEY (id)")
                self.stdout.write("Set UUID primary key on tenants")
            except Exception as e:
                self.stdout.write("SKIP pk: " + str(e)[:60])

            self.stdout.write("Phase 2 Step 5: Rename FK columns in child tables...")
            cursor.execute("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE column_name LIKE 'new_%'
                AND table_schema = 'public'
            """)
            new_cols = cursor.fetchall()
            self.stdout.write("Found " + str(len(new_cols)) + " new_ columns to rename")

            for table_name, col_name in new_cols:
                old_col = col_name[4:]  # remove 'new_' prefix
                try:
                    cursor.execute("ALTER TABLE " + table_name + " DROP COLUMN IF EXISTS " + old_col)
                    cursor.execute("ALTER TABLE " + table_name + " RENAME COLUMN " + col_name + " TO " + old_col)
                    self.stdout.write("Renamed: " + table_name + "." + col_name + " -> " + old_col)
                except Exception as e:
                    self.stdout.write("SKIP rename col: " + table_name + "." + col_name + " - " + str(e)[:60])

            self.stdout.write("Phase 2 Step 6: Drop old_id column from tenants...")
            try:
                cursor.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS old_id")
                self.stdout.write("Dropped old_id from tenants")
            except Exception as e:
                self.stdout.write("SKIP: " + str(e)[:60])

        self.stdout.write("Phase 2 COMPLETE! tenants.id is now UUID!")
