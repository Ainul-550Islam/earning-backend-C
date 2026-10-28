"""
NEW FILE — Data migration that seeds the default RBAC roles and
permissions (admin / editor / viewer, and the Permission rows each one
grants).

This used to be attempted inside `AppConfig.ready()`, but querying/
writing the database during app initialization is discouraged by Django
(it can run before migrations are applied, outside a safe transaction,
and multiple times under some app servers). A data migration is the
correct, idempotent, one-time way to seed this data — it runs exactly
once, in order, tracked by Django's migration state, with the rest of
`migrate`.
"""
from django.db import migrations


ROLE_NAMES = ['admin', 'editor', 'viewer']

PERMISSION_ROLE_MAP = {
    'view_flag': ['admin', 'editor', 'viewer'],
    'create_flag': ['admin', 'editor'],
    'edit_flag': ['admin', 'editor'],
    'delete_flag': ['admin'],
    'start_experiment': ['admin', 'editor'],
    'view_analytics': ['admin', 'editor', 'viewer'],
    'manage_users': ['admin'],
    'approve_changes': ['admin'],
}


def bootstrap_rbac(apps, schema_editor):
    Role = apps.get_model('feature_flags', 'Role')
    Permission = apps.get_model('feature_flags', 'Permission')

    roles_by_name = {}
    for name in ROLE_NAMES:
        role, _ = Role.objects.get_or_create(name=name)
        roles_by_name[name] = role

    for perm_name, role_names in PERMISSION_ROLE_MAP.items():
        perm, _ = Permission.objects.get_or_create(name=perm_name)
        perm.roles.set([roles_by_name[r] for r in role_names])


def unbootstrap_rbac(apps, schema_editor):
    Role = apps.get_model('feature_flags', 'Role')
    Permission = apps.get_model('feature_flags', 'Permission')
    Permission.objects.filter(name__in=PERMISSION_ROLE_MAP.keys()).delete()
    Role.objects.filter(name__in=ROLE_NAMES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('feature_flags', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(bootstrap_rbac, unbootstrap_rbac),
    ]
