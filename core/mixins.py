"""
Mixins cho phân quyền theo role (Quản lý và Nhân viên).
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404


class ManagerRequiredMixin(UserPassesTestMixin):
    """Mixin yêu cầu user phải có role quản lý."""
    
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        profile = getattr(self.request.user, 'profile', None)
        if not profile:
            return False
        return profile.is_manager()
    
    def handle_no_permission(self):
        raise PermissionDenied("Bạn không có quyền truy cập trang này. Chỉ quản lý mới có quyền.")


class EmployeeOrManagerMixin(LoginRequiredMixin):
    """Mixin cho phép cả quản lý và nhân viên truy cập."""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


def is_manager(user):
    """Helper function để check user có phải quản lý không."""
    if not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    if not profile:
        return False
    return profile.is_manager()


def is_employee(user):
    """Helper function để check user có phải nhân viên không."""
    if not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    if not profile:
        return False
    return profile.is_employee()


def get_user_role(user):
    """Lấy role của user."""
    if not user.is_authenticated:
        return None
    profile = getattr(user, 'profile', None)
    if not profile:
        return None
    return profile.role
