from django import forms
from .models import Department, Employee, ResourceAllocation, Position
from decimal import Decimal, InvalidOperation
import re


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description', 'manager']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên phòng ban'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mô tả'}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name': 'Tên phòng ban',
            'description': 'Mô tả',
            'manager': 'Trưởng phòng',
        }


class EmployeeForm(forms.ModelForm):
    position_fk = forms.ModelChoiceField(
        queryset=Position.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_position_fk'
        }),
        label='Chức vụ (từ danh sách)'
    )
    position = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Hoặc nhập chức vụ tùy chỉnh',
            'id': 'id_position'
        }),
        label='Chức vụ tùy chỉnh'
    )
    role = forms.ChoiceField(
        choices=[
            ('employee', 'Nhân viên'),
            ('manager', 'Quản lý'),
        ],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_role'
        }),
        label='Quyền',
        initial='employee',
        help_text='Quyền của người dùng trong hệ thống'
    )

    class Meta:
        model = Employee
        fields = ['employee_id', 'first_name', 'last_name', 'email', 'phone',
                  'department', 'position_fk', 'position', 'employment_type', 'hire_date', 'hourly_rate', 'is_active']
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mã nhân viên'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hourly_rate': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0', 'type': 'text', 'id': 'id_hourly_rate'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'employee_id': 'Mã nhân viên',
            'first_name': 'Tên',
            'last_name': 'Họ',
            'email': 'Email',
            'phone': 'Số điện thoại',
            'department': 'Phòng ban',
            'employment_type': 'Loại hợp đồng',
            'hire_date': 'Ngày tuyển dụng',
            'hourly_rate': 'Mức lương/giờ',
            'is_active': 'Đang hoạt động',
        }

    def clean(self):
        cleaned_data = super().clean()
        position_fk = cleaned_data.get('position_fk')
        position = cleaned_data.get('position', '').strip()
        
        # Nếu không chọn position từ dropdown và không nhập position, báo lỗi
        if not position_fk and not position:
            raise forms.ValidationError({
                'position_fk': 'Vui lòng chọn chức vụ từ danh sách hoặc nhập chức vụ tùy chỉnh.',
                'position': 'Vui lòng chọn chức vụ từ danh sách hoặc nhập chức vụ tùy chỉnh.'
            })
        
        # Nếu chọn từ dropdown, dùng tên của position đó
        if position_fk:
            cleaned_data['position'] = position_fk.name
        
        return cleaned_data

    def clean_hourly_rate(self):
        """
        Parse lương/giờ (VNĐ) từ input text.

        Hỗ trợ các format phổ biến:
        - 85000
        - 85,000
        - 85.000
        - 85 000
        """
        hourly_rate = self.cleaned_data.get('hourly_rate')
        if hourly_rate in (None, ''):
            return hourly_rate

        # Nếu đã là số (Decimal/float/int), giữ nguyên
        if isinstance(hourly_rate, (int, float, Decimal)):
            value = Decimal(str(hourly_rate))
        else:
            raw = str(hourly_rate).strip()
            if raw.startswith('-'):
                raise forms.ValidationError('Mức lương không được âm.')

            # Giữ lại chữ số, loại bỏ mọi ký tự phân cách (., , , space, ...)
            digits_only = re.sub(r'[^\d]', '', raw)
            if digits_only == '':
                raise forms.ValidationError('Vui lòng nhập số hợp lệ.')

            try:
                value = Decimal(digits_only)
            except (InvalidOperation, ValueError):
                raise forms.ValidationError('Vui lòng nhập số hợp lệ.')

        if value < 0:
            raise forms.ValidationError('Mức lương không được âm.')

        return value


class ResourceAllocationForm(forms.ModelForm):
    class Meta:
        model = ResourceAllocation
        fields = ['employee', 'project', 'allocation_percentage', 'start_date', 'end_date', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'allocation_percentage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0-100', 'min': '0', 'max': '100', 'step': '0.01'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ghi chú'}),
        }
        labels = {
            'employee': 'Nhân sự',
            'project': 'Dự án',
            'allocation_percentage': 'Tỷ lệ phân bổ (%)',
            'start_date': 'Ngày bắt đầu',
            'end_date': 'Ngày kết thúc',
            'notes': 'Ghi chú',
        }

