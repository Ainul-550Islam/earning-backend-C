# api/payment_gateways/migration_utils.py
import logging
logger=logging.getLogger(__name__)

MIGRATION_ORDER=['payment_gateways','payment_gateways_refunds','payment_gateways_fraud','payment_gateways_notifications','payment_gateways_reports','payment_gateways_schedules','payment_gateways_referral','payment_gateways_offers','payment_gateways_tracking','payment_gateways_locker','payment_gateways_blacklist','payment_gateways_integrations','payment_gateways_smartlink','payment_gateways_bonuses','payment_gateways_support','payment_gateways_publisher']

def get_migration_commands():
    cmds=['# Run migrations in this order:']
    for app in MIGRATION_ORDER:
        cmds.append(f'python manage.py migrate {app}')
    cmds.append('# Load fixtures:')
    cmds.append('python manage.py loaddata api/payment_gateways/fixtures/gateways.json')
    cmds.append('python manage.py loaddata api/payment_gateways/fixtures/currencies.json')
    return '\n'.join(cmds)

def check_migrations_applied():
    try:
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connection
        executor=MigrationExecutor(connection)
        targets=executor.loader.graph.leaf_nodes()
        plan=executor.migration_plan(targets)
        return {'pending':len(plan),'applied':len(targets)-len(plan)}
    except Exception as e:
        return {'error':str(e)}

def run_post_migration_setup():
    try:
        from api.payment_gateways.models.core import PaymentGateway,Currency
        need_gw=not PaymentGateway.objects.exists()
        need_cur=not Currency.objects.exists()
        if need_gw or need_cur:
            from api.payment_gateways.seed_data import seed_gateways,seed_currencies
            result={}
            if need_gw: result['gateways']=seed_gateways()
            if need_cur: result['currencies']=seed_currencies()
            return result
        return {'status':'already_seeded'}
    except Exception as e:
        return {'status':'error','error':str(e)}
