from django.apps import AppConfig
from django.core.management import call_command
from django.db import connection
import os


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    _migrations_run = False
    
    def ready(self):
        """Tự động chạy migrations khi app khởi động (chỉ chạy một lần)."""
        # Chỉ chạy khi không phải trong quá trình migrate hoặc test
        if os.environ.get('RUN_MAIN') != 'true':
            return
        
        # Chỉ chạy một lần
        if CoreConfig._migrations_run:
            return
        
        # Kiểm tra xem có đang chạy runserver không
        import sys
        if 'runserver' not in ' '.join(sys.argv):
            return
        
        try:
            # Tự động tạo migrations
            try:
                call_command('makemigrations', verbosity=0, interactive=False)
            except Exception:
                pass  # Bỏ qua lỗi khi tạo migrations
            
            # Tự động chạy migrations
            try:
                call_command('migrate', verbosity=0, interactive=False)
            except Exception:
                pass  # Bỏ qua lỗi khi chạy migrations
            
            CoreConfig._migrations_run = True
        except Exception:
            pass  # Bỏ qua tất cả lỗi để không ảnh hưởng đến server

