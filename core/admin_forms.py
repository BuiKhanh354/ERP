"""
Forms cho User Management trong Admin Panel — RBAC-aware.
"""
from django import forms
from django.contrib.auth.models import User
from core.models import Role, UserRole
from resources.models import Department


class AdminUserCreateForm(forms.Form):
    """Form tạo user mới — gán role RBAC, phòng ban."""
    first_name = forms.CharField(
        max_length=150, label='Họ',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nguyễn Văn'}),
    )
    last_name = forms.CharField(
        max_length=150, label='Tên',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'A'}),
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'user@example.com'}),
    )
    username = forms.CharField(
        max_length=150, label='Username',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'username'}),
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        label='Roles',
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        label='Phòng ban',
        required=False,
        empty_label='-- Chọn phòng ban --',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    is_active = forms.BooleanField(
        label='Active', required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username đã tồn tại.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email đã được sử dụng.')
        return email

    def save(self):
        """Tạo user + gán roles."""
        data = self.cleaned_data
        # Tạo user với password tạm thời (user sẽ tự đặt qua email kích hoạt)
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            is_active=data['is_active'],
        )
        # Đặt password tạm — user phải đổi khi đăng nhập lần đầu
        import secrets
        temp_password = secrets.token_urlsafe(12)
        user.set_password(temp_password)
        user.save()

        # Gán roles RBAC và kiểm tra quyền admin
        is_admin = False
        for role in data.get('roles', []):
            UserRole.objects.get_or_create(user=user, role=role)
            if role.name.upper() == 'ADMIN':
                is_admin = True
                
        # Cập nhật is_staff tự động dựa trên role admin
        user.is_staff = is_admin
        user.save()

        # Tạo UserProfile
        from core.models import UserProfile
        UserProfile.objects.get_or_create(user=user)

        return user, temp_password


class AdminUserEditForm(forms.Form):
    """Form chỉnh sửa user — đổi role, department, active/staff, reset password."""
    first_name = forms.CharField(
        max_length=150, label='Họ',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        max_length=150, label='Tên',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        label='Roles',
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        label='Phòng ban',
        required=False,
        empty_label='-- Chọn phòng ban --',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    is_active = forms.BooleanField(
        label='Active', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    reset_password = forms.BooleanField(
        label='Reset mật khẩu (tạo password mới tạm thời)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, user_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_obj = user_obj
        if user_obj:
            self.fields['first_name'].initial = user_obj.first_name
            self.fields['last_name'].initial = user_obj.last_name
            self.fields['email'].initial = user_obj.email
            self.fields['is_active'].initial = user_obj.is_active
            # Get current roles
            current_role_ids = UserRole.objects.filter(user=user_obj).values_list('role_id', flat=True)
            self.fields['roles'].initial = current_role_ids
            # Get current department from Employee
            from resources.models import Employee
            try:
                emp = Employee.objects.get(user=user_obj)
                self.fields['department'].initial = emp.department_id
            except Employee.DoesNotExist:
                pass

    def clean_email(self):
        email = self.cleaned_data['email']
        if self.user_obj and User.objects.filter(email=email).exclude(pk=self.user_obj.pk).exists():
            raise forms.ValidationError('Email đã được sử dụng bởi user khác.')
        return email

    def save(self):
        """Cập nhật user + roles."""
        data = self.cleaned_data
        user = self.user_obj

        old_active = user.is_active
        old_roles = set(UserRole.objects.filter(user=user).values_list('role__name', flat=True))

        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.email = data['email']
        user.is_active = data['is_active']
        user.save()

        # Sync roles — xóa cũ + tạo mới
        UserRole.objects.filter(user=user).delete()
        is_admin = False
        for role in data.get('roles', []):
            UserRole.objects.create(user=user, role=role)
            if role.name.upper() == 'ADMIN':
                is_admin = True
                
        user.is_staff = is_admin
        user.save()

        new_password = None
        if data.get('reset_password'):
            import secrets
            new_password = secrets.token_urlsafe(12)
            user.set_password(new_password)
            user.save()

        # Return changes for audit log
        new_roles = set(r.name for r in data.get('roles', []))
        changes = {}
        if old_active != data['is_active']:
            changes['is_active'] = {'old': old_active, 'new': data['is_active']}
        if old_roles != new_roles:
            changes['roles'] = {'old': list(old_roles), 'new': list(new_roles)}
        if data.get('reset_password'):
            changes['password'] = 'reset'

        return user, new_password, changes
