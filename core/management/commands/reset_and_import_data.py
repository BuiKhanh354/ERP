"""
Management command để xóa data mẫu và import data thực trong một lệnh.
Chạy: python manage.py reset_and_import_data --confirm
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Xóa data mẫu và import data thực (chạy cả 2 bước)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Xác nhận reset và import data (bắt buộc)',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '[WARNING] CANH BAO: Lenh nay se:\n'
                    '   1. Xoa TOAN BO data mau hien co\n'
                    '   2. Import data thuc va gan cho 2 user chinh\n\n'
                    'De xac nhan, chay: python manage.py reset_and_import_data --confirm'
                )
            )
            return

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('BAT DAU RESET VA IMPORT DATA'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Bước 1: Xóa data mẫu
        self.stdout.write(self.style.WARNING('\n[STEP 1] Dang xoa data mau...'))
        try:
            call_command('clear_sample_data', '--confirm')
            self.stdout.write(self.style.SUCCESS('[OK] Da xoa data mau thanh cong\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[ERROR] Loi khi xoa data mau: {e}'))
            return

        # Bước 2: Import data thực
        self.stdout.write(self.style.WARNING('[STEP 2] Dang import data thuc...'))
        try:
            call_command('import_real_data', '--confirm')
            self.stdout.write(self.style.SUCCESS('[OK] Da import data thuc thanh cong\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[ERROR] Loi khi import data: {e}'))
            return

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('HOAN TAT! Data da duoc reset va import thanh cong.'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('\n[INFO] Kiem tra:'))
        self.stdout.write('   - Dang nhap voi: thanhhung111120021@gmail.com (quan ly)')
        self.stdout.write('   - Dang nhap voi: nthung.viettin@gmail.com (nhan vien)')
