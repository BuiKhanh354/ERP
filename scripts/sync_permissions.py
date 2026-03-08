import os
import sys
import django
import ast
import glob

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ERP.settings')
django.setup()

from core.models import Permission

def extract_permissions_from_views(app_path):
    """
    Quét tất cả files .py trong app_path (thường là views.py)
    Tìm các class kế thừa PermissionRequiredMixin và có thuộc tính permission_required
    """
    found_permissions = set()
    
    for filename in glob.iglob(app_path + '**/*.py', recursive=True):
        if 'venv' in filename or '.venv' in filename:
            continue
            
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                node = ast.parse(file.read(), filename=filename)
                
            for child in ast.walk(node):
                if isinstance(child, ast.ClassDef):
                    # Check if inherits from PermissionRequiredMixin
                    inherits_permission_mixin = any(
                        getattr(base, 'id', '') == 'PermissionRequiredMixin' 
                        for base in child.bases
                    )
                    
                    if inherits_permission_mixin:
                        for body_item in child.body:
                            if isinstance(body_item, ast.Assign):
                                for target in body_item.targets:
                                    if getattr(target, 'id', '') == 'permission_required':
                                        val = body_item.value
                                        if isinstance(val, ast.Constant):
                                            found_permissions.add(val.value)
                                        elif isinstance(val, ast.List) or isinstance(val, ast.Tuple):
                                            for elt in val.elts:
                                                if isinstance(elt, ast.Constant):
                                                    found_permissions.add(elt.value)
        except Exception as e:
            print(f"Lỗi khi đọc file {filename}: {e}")

    return found_permissions

def check_permissions_sync():
    print(" Bắt đầu kiểm tra đồng bộ Permission Matrix...")
    
    # Lấy set permissions từ Database
    db_permissions = set(Permission.objects.values_list('code', flat=True))
    
    # Lấy set permissions từ Codebase (quét thư mục gốc của project)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code_permissions = extract_permissions_from_views(project_root + '/')
    
    # 1. Check Orphan Code Permissions (Có trong code, chưa có trong DB)
    orphans_in_code = code_permissions - db_permissions
    
    # 2. Check Unused DB Permissions (Có trong DB, không thấy dùng trong view classes)
    # Note: DB permissions có thể được dùng trong templates (e.g., {% if '...' in user_permissions %})
    # Do vậy, kết quả này chỉ tham khảo.
    unused_in_views = db_permissions - code_permissions
    
    print("\n--- Báo cáo Đồng Bộ ---")
    
    if orphans_in_code:
        print(f"\n [CẢNH BÁO] Có {len(orphans_in_code)} permissions được dùng trong Views nhưng CHƯA TỒN TẠI trong Database:")
        for p in orphans_in_code:
            print(f"  - {p}")
        print("  -> Hành động: Vui lòng thêm các permission này vào Database hoặc Admin Panel.")
    else:
        print("\n [OK] Mọi permission yêu cầu trong Views đều đã tồn tại trong Database.")
        
    if unused_in_views:
        print(f"\n [THÔNG TIN] Có {len(unused_in_views)} permissions trong Database nhưng KHÔNG sử dụng qua `permission_required` trong Views:")
        print("  (Lưu ý: Chúng có thể đang được kiểm tra trực tiếp qua code hoặc templates)")
        for p in list(unused_in_views)[:10]:  # Print first 10
            print(f"  - {p}")
        if len(unused_in_views) > 10:
            print(f"  ... và {len(unused_in_views) - 10} permissions khác.")

if __name__ == "__main__":
    check_permissions_sync()
