"""
RBAC (Role-Based Access Control) — Service helpers.

Cung cấp các hàm kiểm tra quyền theo mô hình:
    User → UserRole → Role → RolePermission → Permission
    
Sử dụng:
    from core.rbac import has_permission, get_user_permissions
    
    if has_permission(request.user, 'create_project'):
        ...
"""
from functools import lru_cache
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


def get_user_roles(user):
    """Trả về danh sách Role objects của user."""
    if not user or not user.is_authenticated:
        return []
    from core.models import Role
    return list(
        Role.objects.filter(
            user_roles__user=user,
            is_active=True,
        ).distinct()
    )


def get_user_role_names(user):
    """Trả về set tên role của user."""
    return {r.name for r in get_user_roles(user)}


def get_user_permissions(user):
    """Trả về set permission codes mà user có (qua tất cả roles)."""
    if not user or not user.is_authenticated:
        return set()
    from core.models import Permission
    codes = Permission.objects.filter(
        role_permissions__role__user_roles__user=user,
        role_permissions__role__is_active=True,
    ).values_list('code', flat=True).distinct()
    return set(codes)


def has_permission(user, permission_code):
    """Kiểm tra user có permission_code hay không."""
    if not user or not user.is_authenticated:
        return False
    # Superuser luôn có mọi quyền
    if user.is_superuser:
        return True
    perms = get_user_permissions(user)
    return permission_code in perms


def has_any_permission(user, *permission_codes):
    """Kiểm tra user có ít nhất 1 trong các permission codes."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perms = get_user_permissions(user)
    return bool(perms & set(permission_codes))


def has_all_permissions(user, *permission_codes):
    """Kiểm tra user có tất cả permission codes."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perms = get_user_permissions(user)
    return set(permission_codes).issubset(perms)


def has_role(user, role_name):
    """Kiểm tra user có role nào đó không."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return role_name in get_user_role_names(user)


def log_audit(user, action_type, table_name, record_id='', old_data=None, new_data=None, ip_address=None):
    """Ghi audit log."""
    from core.models import AuditLog
    AuditLog.objects.create(
        user=user,
        action_type=action_type,
        table_name=table_name,
        record_id=str(record_id),
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address,
    )


def get_client_ip(request):
    """Lấy IP address từ request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ============================================================
# Django Mixins cho RBAC
# ============================================================

class PermissionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin kiểm tra permission RBAC.
    
    Sử dụng:
        class MyView(PermissionRequiredMixin, ...):
            permission_required = 'create_project'
            # hoặc nhiều permissions:
            permission_required = ['create_project', 'edit_project']
    """
    permission_required = None  # str hoặc list[str]

    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        if self.request.user.is_superuser:
            return True
        perm = self.permission_required
        if perm is None:
            return True
        if isinstance(perm, str):
            return has_permission(self.request.user, perm)
        # list — user phải có ít nhất 1
        return has_any_permission(self.request.user, *perm)

    def handle_no_permission(self):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Bạn không có quyền truy cập chức năng này.")
