from django import forms
from resources.models import Department, Employee


class AdminDepartmentForm(forms.ModelForm):
    """Form quản lý phòng ban dành cho Admin."""

    class Meta:
        model = Department
        fields = ['name', 'code', 'parent', 'manager', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập tên phòng ban',
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'VD: FIN, ENG, HR',
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select',
            }),
            'manager': forms.Select(attrs={
                'class': 'form-select',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Mô tả phòng ban',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'name': 'Tên phòng ban',
            'code': 'Mã phòng ban',
            'parent': 'Phòng ban cha',
            'manager': 'Trưởng phòng',
            'description': 'Mô tả',
            'is_active': 'Đang hoạt động',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Loại bỏ chính nó ra khỏi danh sách parent để tránh vòng lặp
        if self.instance and self.instance.pk:
            descendants = self.instance.get_descendants()
            exclude_ids = [d.pk for d in descendants] + [self.instance.pk]
            self.fields['parent'].queryset = Department.objects.exclude(pk__in=exclude_ids)
        else:
            self.fields['parent'].queryset = Department.objects.all()

        self.fields['parent'].required = False
        self.fields['parent'].empty_label = '— Không có (Phòng ban gốc) —'

        # Chỉ hiển thị nhân viên đang active
        self.fields['manager'].queryset = Employee.objects.filter(is_active=True)
        self.fields['manager'].required = False
        self.fields['manager'].empty_label = '— Chưa chỉ định —'

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if code:
            qs = Department.objects.filter(code=code)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Mã phòng ban đã tồn tại.')
        return code

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get('parent')
        if parent and self.instance and self.instance.pk:
            if parent.pk == self.instance.pk:
                raise forms.ValidationError({
                    'parent': 'Phòng ban không thể là cha của chính nó.'
                })
        return cleaned_data
