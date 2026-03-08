#!/usr/bin/env python
"""
Script wrapper để tự động tạo database, migrations và chạy migrations trước khi khởi động Django development server.

Sử dụng:
    python runserver.py localhost:8000
    python runserver.py 0.0.0.0:8000
    python runserver.py 8000
    python runserver.py  # Mặc định localhost:8000
    python runserver.py --no-sample-users  # Bỏ qua tạo user mẫu
"""
import os
import sys
import django
import importlib.util
from pathlib import Path

# Thiết lập Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ERP.settings')
django.setup()

from django.core.management import call_command
from django.core.management.color import no_style
from django.db import connection
from django.conf import settings

try:
    import pyodbc
except ImportError:
    pyodbc = None


def create_database_if_not_exists():
    """Tự động tạo database nếu chưa tồn tại (chỉ cho SQL Server)."""
    db_config = settings.DATABASES['default']
    
    # Chỉ xử lý cho SQL Server
    if db_config['ENGINE'] not in ('mssql', 'mssql.django'):
        return True
    
    # Kiểm tra pyodbc có sẵn không
    if pyodbc is None:
        print('⚠ pyodbc chưa được cài đặt. Không thể tự động tạo database.')
        print('Vui lòng cài đặt: pip install pyodbc')
        return False
    
    db_name = db_config.get('NAME')
    db_user = db_config.get('USER', '')
    db_password = db_config.get('PASSWORD', '')
    db_host = db_config.get('HOST', 'localhost')
    db_port = db_config.get('PORT', '')
    
    options = db_config.get('OPTIONS', {})
    driver = options.get('driver', 'ODBC Driver 17 for SQL Server')
    
    try:
        # Kết nối đến SQL Server (không chỉ định database cụ thể)
        server_str = f"{db_host},{db_port}" if db_port else db_host
        
        conn_parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server_str}"
        ]
        
        if db_user:
            conn_parts.append(f"UID={db_user}")
        if db_password:
            conn_parts.append(f"PWD={db_password}")
            
        for key, value in options.items():
            if key.lower() != 'driver':
                conn_parts.append(f"{key}={value}")
                
        # Hỗ trợ thêm các option bắt buộc với một số driver
        options_lower = {k.lower(): v for k, v in options.items()}
        if '18' in driver and 'encrypt' not in options_lower:
            conn_parts.append("Encrypt=yes")
        if 'trustservercertificate' not in options_lower:
            conn_parts.append("TrustServerCertificate=yes")
            
        conn_str = ";".join(conn_parts) + ";"
        
        # Kết nối đến master database để kiểm tra/tạo database
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        
        # Kiểm tra xem database đã tồn tại chưa
        cursor.execute("""
            SELECT name FROM sys.databases WHERE name = ?
        """, db_name)
        
        if cursor.fetchone():
            print(f'✓ Database "{db_name}" đã tồn tại')
            cursor.close()
            conn.close()
            return True
        
        # Tạo database mới
        print(f'Đang tạo database "{db_name}"...')
        cursor.execute(f"CREATE DATABASE [{db_name}]")
        cursor.close()
        conn.close()
        
        print(f'✓ Đã tạo database "{db_name}" thành công')
        return True
        
    except Exception as e:
        print(f'⚠ Không thể tự động tạo database: {str(e)}')
        print('Vui lòng tạo database thủ công hoặc kiểm tra quyền truy cập.')
        # Không exit, để tiếp tục thử kết nối với database hiện có
        return False

def create_sample_users_if_needed():
    """Tạo user mẫu tự động - chỉ tạo các user chưa tồn tại."""
    # Import và chạy script tạo user mẫu
    # Script sẽ tự kiểm tra và chỉ tạo user chưa tồn tại
    try:
        script_path = BASE_DIR / 'scripts' / 'create_sample_users.py'
        if script_path.exists():
            print('Đang kiểm tra và tạo user mẫu...')
            # Import module và chạy hàm
            spec = importlib.util.spec_from_file_location("create_sample_users", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.create_sample_users()
            print('✓ Đã kiểm tra và tạo user mẫu thành công')
        else:
            print('⚠ Không tìm thấy script create_sample_users.py')
    except Exception as e:
        print(f'⚠ Lỗi khi tạo user mẫu: {str(e)}')
        print('Bạn có thể tạo user thủ công sau.')


def main():
    """Tạo database, chạy migrations và khởi động server."""
    print('=' * 60)
    print('Đang kiểm tra và thiết lập database...')
    print('=' * 60)
    
    # Kiểm tra flag --no-sample-users
    create_users = '--no-sample-users' not in sys.argv
    if not create_users:
        sys.argv.remove('--no-sample-users')
    
    try:
        # Bước 0: Tạo database nếu chưa tồn tại
        print('\n[0/5] Đang kiểm tra database...')
        create_database_if_not_exists()
        
        # Bước 1: Tạo migrations tự động
        print('\n[1/5] Đang tạo migrations...')
        try:
            call_command('makemigrations', verbosity=1, interactive=False)
            print('✓ Đã kiểm tra migrations')
        except Exception as e:
            print(f'⚠ Lưu ý khi tạo migrations: {str(e)}')
        
        # Bước 2: Chạy migrations để tạo/cập nhật bảng
        print('\n[2/5] Đang chạy migrations...')
        try:
            call_command('migrate', verbosity=1, interactive=False)
            print('✓ Đã chạy migrations thành công')
        except Exception as e:
            print(f'✗ Lỗi khi chạy migrations: {str(e)}')
            print('Vui lòng kiểm tra kết nối database và thử lại.')
            sys.exit(1)
        
        # Bước 3: Kiểm tra kết nối database
        print('\n[3/5] Đang kiểm tra kết nối database...')
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            print('✓ Kết nối database thành công')
        except Exception as e:
            print(f'✗ Lỗi kết nối database: {str(e)}')
            print('Vui lòng kiểm tra cấu hình database trong settings.py')
            sys.exit(1)
        
        # Bước 4: Tạo user mẫu (nếu cần)
        if create_users:
            print('\n[4/5] Đang kiểm tra và tạo user mẫu...')
            create_sample_users_if_needed()
        else:
            print('\n[4/5] Bỏ qua tạo user mẫu (--no-sample-users)')
        
        print('\n[5/5] Đang khởi động development server...')
        print('\n' + '=' * 60)
        print('Server đã sẵn sàng!')
        print('=' * 60 + '\n')
        
        # Bước 5: Khởi động server
        addrport = sys.argv[1] if len(sys.argv) > 1 else 'localhost:8000'
        
        # Chuẩn hóa addrport
        if ':' not in addrport:
            if addrport.isdigit():
                addrport = f'127.0.0.1:{addrport}'
            else:
                addrport = f'127.0.0.1:8000'
        elif addrport.startswith('localhost:'):
            addrport = addrport.replace('localhost:', '127.0.0.1:')
        
        # Chạy runserver
        call_command('runserver', addrport)
        
    except KeyboardInterrupt:
        print('\n\nĐã dừng server.')
        sys.exit(0)
    except Exception as e:
        print(f'\n✗ Lỗi: {str(e)}')
        sys.exit(1)


if __name__ == '__main__':
    main()
