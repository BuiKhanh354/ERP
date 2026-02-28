"""
Custom runserver command để tự động tạo database, migrations và chạy migrations trước khi khởi động server.

Lệnh này sẽ:
1. Tự động tạo database nếu chưa tồn tại
2. Tự động tạo migrations nếu có thay đổi models
3. Tự động chạy migrations để tạo/cập nhật bảng trong database
4. Sau đó khởi động Django development server

Sử dụng:
    python manage.py runserver localhost:8000
    python manage.py runserver 0.0.0.0:8000
    python manage.py runserver 8000
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.core.management.color import no_style
from django.db import connection
from django.conf import settings
import sys

try:
    import pyodbc
except ImportError:
    pyodbc = None


class Command(BaseCommand):
    help = 'Tự động chạy migrations và khởi động development server'

    def add_arguments(self, parser):
        # Thêm các arguments giống runserver mặc định
        parser.add_argument(
            'addrport',
            nargs='?',
            help='Optional port number, or ipaddr:port'
        )
        parser.add_argument(
            '--noreload',
            action='store_true',
            help='Tắt auto-reloader'
        )
        parser.add_argument(
            '--nothreading',
            action='store_true',
            help='Tắt threading'
        )
        parser.add_argument(
            '--ipv6',
            '-6',
            action='store_true',
            dest='use_ipv6',
            help='Sử dụng IPv6'
        )

    def create_database_if_not_exists(self):
        """Tự động tạo database nếu chưa tồn tại (chỉ cho SQL Server)."""
        db_config = settings.DATABASES['default']
        
        # Chỉ xử lý cho SQL Server
        if db_config['ENGINE'] != 'mssql':
            return True
        
        # Kiểm tra pyodbc có sẵn không
        if pyodbc is None:
            self.stdout.write(self.style.WARNING('⚠ pyodbc chưa được cài đặt. Không thể tự động tạo database.'))
            self.stdout.write(self.style.WARNING('Vui lòng cài đặt: pip install pyodbc'))
            return False
        
        db_name = db_config['NAME']
        db_user = db_config['USER']
        db_password = db_config['PASSWORD']
        db_host = db_config['HOST']
        db_port = db_config['PORT']
        driver = db_config['OPTIONS'].get('driver', 'ODBC Driver 17 for SQL Server')
        
        try:
            # Kết nối đến SQL Server (không chỉ định database cụ thể)
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={db_host},{db_port};"
                f"UID={db_user};"
                f"PWD={db_password};"
                f"TrustServerCertificate=yes;"
            )
            
            # Kết nối đến master database để kiểm tra/tạo database
            conn = pyodbc.connect(conn_str, autocommit=True)
            cursor = conn.cursor()
            
            # Kiểm tra xem database đã tồn tại chưa
            cursor.execute("""
                SELECT name FROM sys.databases WHERE name = ?
            """, db_name)
            
            if cursor.fetchone():
                self.stdout.write(self.style.SUCCESS(f'✓ Database "{db_name}" đã tồn tại'))
                cursor.close()
                conn.close()
                return True
            
            # Tạo database mới
            self.stdout.write(self.style.WARNING(f'Đang tạo database "{db_name}"...'))
            cursor.execute(f"CREATE DATABASE [{db_name}]")
            cursor.close()
            conn.close()
            
            self.stdout.write(self.style.SUCCESS(f'✓ Đã tạo database "{db_name}" thành công'))
            return True
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠ Không thể tự động tạo database: {str(e)}'))
            self.stdout.write(self.style.WARNING('Vui lòng tạo database thủ công hoặc kiểm tra quyền truy cập.'))
            # Không exit, để tiếp tục thử kết nối với database hiện có
            return False

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Đang kiểm tra và thiết lập database...'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        try:
            # Bước 0: Tạo database nếu chưa tồn tại
            self.stdout.write(self.style.WARNING('\n[0/4] Đang kiểm tra database...'))
            self.create_database_if_not_exists()
            
            # Bước 1: Tạo migrations tự động
            self.stdout.write(self.style.WARNING('\n[1/4] Đang tạo migrations...'))
            try:
                call_command('makemigrations', verbosity=1, interactive=False)
                self.stdout.write(self.style.SUCCESS('✓ Đã kiểm tra migrations'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠ Lưu ý khi tạo migrations: {str(e)}'))
            
            # Bước 2: Chạy migrations để tạo/cập nhật bảng
            self.stdout.write(self.style.WARNING('\n[2/4] Đang chạy migrations...'))
            try:
                call_command('migrate', verbosity=1, interactive=False)
                self.stdout.write(self.style.SUCCESS('✓ Đã chạy migrations thành công'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Lỗi khi chạy migrations: {str(e)}'))
                self.stdout.write(self.style.ERROR('Vui lòng kiểm tra kết nối database và thử lại.'))
                sys.exit(1)
            
            # Bước 3: Kiểm tra kết nối database
            self.stdout.write(self.style.WARNING('\n[3/4] Đang kiểm tra kết nối database...'))
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                self.stdout.write(self.style.SUCCESS('✓ Kết nối database thành công'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Lỗi kết nối database: {str(e)}'))
                self.stdout.write(self.style.ERROR('Vui lòng kiểm tra cấu hình database trong settings.py'))
                sys.exit(1)
            
            self.stdout.write(self.style.SUCCESS('\n[4/4] Đang khởi động development server...'))
            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            self.stdout.write(self.style.SUCCESS('Server đã sẵn sàng!'))
            self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))
            
            # Bước 4: Khởi động server (gọi runserver gốc)
            # Lấy addrport từ options
            addrport = options.get('addrport', '8000')
            
            # Chuẩn hóa addrport
            if addrport:
                # Xử lý các định dạng: localhost:8000, 0.0.0.0:8000, 8000, 127.0.0.1:8000
                if ':' in addrport:
                    # Đã có địa chỉ IP và port
                    if addrport.startswith('localhost:'):
                        addrport = addrport.replace('localhost:', '127.0.0.1:')
                else:
                    # Chỉ có port, mặc định là 127.0.0.1
                    if addrport.isdigit():
                        addrport = f'127.0.0.1:{addrport}'
            else:
                addrport = '127.0.0.1:8000'
            
            # Gọi runserver gốc của Django
            from django.core.management.commands.runserver import Command as RunserverCommand
            runserver = RunserverCommand()
            
            # Truyền các options
            runserver_options = {
                'addrport': addrport,
                'noreload': options.get('noreload', False),
                'nothreading': options.get('nothreading', False),
                'use_ipv6': options.get('use_ipv6', False),
            }
            
            # Chạy runserver
            runserver.handle(*args, **runserver_options)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n\nĐã dừng server.'))
            sys.exit(0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Lỗi: {str(e)}'))
            sys.exit(1)
