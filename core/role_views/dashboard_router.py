from django.views.generic import View
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from core.rbac import get_user_role_names

class DashboardRouterView(LoginRequiredMixin, View):
    """
    Theo cấu trúc mới (Role-Based UI), sau khi người dùng đăng nhập
    sẽ được điều hướng về trang Dashboard của role tương ứng
    """
    def get(self, request, *args, **kwargs):
        role_names = get_user_role_names(request.user)
        if request.user.is_superuser or 'ADMIN' in role_names:
            return redirect('admin_custom:dashboard')
        if 'MANAGER' in role_names:
            return redirect('pm_module:dashboard')
        if 'FINANCE' in role_names:
            return redirect('budgeting:manage')
        return redirect('employee_module:dashboard')
