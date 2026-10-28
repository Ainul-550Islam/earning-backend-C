from django.db import migrations


class Migration(migrations.Migration):
    """
    No-op stand-in for the host project's real tenants migration of the same
    name. Only exists so messaging's migration graph (which depends on it)
    resolves when messaging is tested standalone, without the real `tenants`
    app on INSTALLED_APPS. See messaging/tests/_tenant_stub/apps.py.
    """

    dependencies = [
        ("tenants", "0003_planfeature_planquota_planupgrade_planusage_and_more"),
    ]

    operations = []
