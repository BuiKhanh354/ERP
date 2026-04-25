from django.core.management.base import BaseCommand
from django.db import connection


TARGET_TABLES = [
    'accounting_invoice',
    'accounting_invoiceitem',
    'accounting_payment',
    'accounting_vendorbill',
    'accounting_vendorbillitem',
    'accounting_vendorpayment',
    'performance_performancemetric',
    'performance_performancescore',
    'clients_contact',
    'clients_clientinteraction',
    'resources_skill',
    'resources_employeeskill',
    'resources_payrollschedule',
    'resources_employeehourlyrate',
    'projects_milestone',
    'projects_personnelrecommendation',
    'projects_personnelrecommendationdetail',
    'projects_projectmembershiprequest',
    'core_accountdeleteotp',
    'core_emailchangeotp',
    'core_passwordresetotp',
    'auth_group',
    'auth_group_permissions',
    'auth_user_groups',
    'auth_user_user_permissions',
    'django_admin_log',
    'budgeting_financialforecast',
    'ai_aiinsight',
]


class Command(BaseCommand):
    help = 'Trim database schema for compact scope (target ~30 tables).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what will be dropped')
        parser.add_argument('--force', action='store_true', help='Actually drop tables')

    def handle(self, *args, **options):
        dry_run = options['dry_run'] or not options['force']

        with connection.cursor() as cur:
            cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
            existing = {r[0] for r in cur.fetchall()}

        drop_tables = [t for t in TARGET_TABLES if t in existing]
        missing = [t for t in TARGET_TABLES if t not in existing]

        self.stdout.write(f'Target tables: {len(TARGET_TABLES)}')
        self.stdout.write(f'Existing to drop: {len(drop_tables)}')
        self.stdout.write(f'Already missing: {len(missing)}')

        if drop_tables:
            self.stdout.write('Will drop tables:')
            for t in drop_tables:
                self.stdout.write(f'  - {t}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN mode. No changes applied.'))
            return

        with connection.cursor() as cur:
            # Drop FKs where parent or referenced table in drop set
            placeholders = ','.join(['%s'] * len(drop_tables))
            fk_sql = f"""
                SELECT fk.name, tp.name AS parent_table
                FROM sys.foreign_keys fk
                JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
                JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
                WHERE tp.name IN ({placeholders}) OR tr.name IN ({placeholders})
            """
            cur.execute(fk_sql, drop_tables + drop_tables)
            fk_rows = cur.fetchall()

            for fk_name, parent_table in fk_rows:
                cur.execute(f"ALTER TABLE [{parent_table}] DROP CONSTRAINT [{fk_name}]")
                self.stdout.write(f'Dropped FK: {parent_table}.{fk_name}')

            for table in drop_tables:
                cur.execute(f"DROP TABLE [{table}]")
                self.stdout.write(self.style.SUCCESS(f'Dropped table: {table}'))

            cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
            remaining = cur.fetchone()[0]

        self.stdout.write(self.style.SUCCESS(f'Trim completed. Remaining BASE TABLE count: {remaining}'))
