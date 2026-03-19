from django.core.management.base import BaseCommand
from django.apps import apps
import importlib

class Command(BaseCommand):
    help = 'Check all serializers for invalid fields'

    def handle(self, *args, **kwargs):
        errors = []
        for app in apps.get_app_configs():
            try:
                mod = importlib.import_module(f'{app.name}.serializers')
                for name in dir(mod):
                    cls = getattr(mod, name)
                    try:
                        if hasattr(cls, 'Meta') and hasattr(cls.Meta, 'fields') and hasattr(cls.Meta, 'model'):
                            model = cls.Meta.model
                            if model and isinstance(cls.Meta.fields, list):
                                model_fields = [f.name for f in model._meta.get_fields()]
                                for field in cls.Meta.fields:
                                    if field not in model_fields and not hasattr(cls, field):
                                        errors.append(f'[BAD FIELD] {app.name}.{name}: {field}')
                    except: pass
            except: pass

        if errors:
            for e in errors:
                self.stdout.write(self.style.ERROR(e))
        else:
            self.stdout.write(self.style.SUCCESS('NO ERRORS FOUND'))
