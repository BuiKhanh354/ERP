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
        elif 'HR_ADMIN' in role_names:
            return redirect('hr_module:dashboard')
        elif 'PROJECT_MANAGER' in role_names:
            return redirect('pm_module:dashboard')
        elif 'EXECUTIVE' in role_names:
            return redirect('executive_module:dashboard')
        elif 'RESOURCE_MANAGER' in role_names:
            return redirect('resource_manager_module:dashboard')
        elif 'FINANCE_ADMIN' in role_names:
            return redirect('finance_admin_module:dashboard')
        elif 'ACCOUNTANT' in role_names:
            return redirect('accountant_module:dashboard')
        elif 'EMPLOYEE' in role_names:
            return redirect('employee_module:dashboard')
        else:
            return redirect('employee_module:dashboard')
