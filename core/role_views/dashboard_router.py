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
        
        if 'Admin' in role_names or request.user.is_superuser:
            return redirect('admin_custom:dashboard')
        elif 'CFO' in role_names:
            return redirect('cfo:dashboard')
        elif 'HR' in role_names:
            return redirect('hr_module:dashboard')
        elif 'Project Manager' in role_names:
            return redirect('pm_module:dashboard')
        else:
            return redirect('employee_module:dashboard')
