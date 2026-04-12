# management/commands/seed_timezones.py
"""python manage.py seed_timezones — all IANA timezones seed করে"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'All IANA timezones seed করে'

    def handle(self, *args, **options):
        import pytz
        from localization.models.core import Timezone
        from django.utils import timezone as dj_tz
        created = skipped = 0
        for tz_name in pytz.all_timezones:
            try:
                tz = pytz.timezone(tz_name)
                now = dj_tz.now().astimezone(tz)
                offset = now.utcoffset()
                total_secs = int(offset.total_seconds())
                sign = '+' if total_secs >= 0 else '-'
                hrs, rem = divmod(abs(total_secs), 3600)
                mins = rem // 60
                offset_str = f"{sign}{hrs:02d}:{mins:02d}"
                parts = tz_name.split('/')
                code = parts[-1].upper()[:50] if parts else tz_name[:50]
                _, was_created = Timezone.objects.get_or_create(
                    name=tz_name,
                    defaults={
                        'code': code,
                        'offset': offset_str,
                        'offset_seconds': total_secs,
                        'region': parts[0] if len(parts) > 1 else '',
                    }
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            except Exception as e:
                self.stderr.write(f"Failed for {tz_name}: {e}")
        self.stdout.write(self.style.SUCCESS(f'Timezones seeded: {created} created, {skipped} skipped'))
