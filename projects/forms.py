from django import forms
from decimal import Decimal, InvalidOperation
from .models import Project, Task, TimeEntry
from resources.models import Department


class ProjectForm(forms.ModelForm):
    # Override choices với tiếng Việt
    STATUS_CHOICES = [
        ('planning', 'Lên kế hoạch'),
        ('active', 'Đang chạy'),
        ('on_hold', 'Tạm dừng'),
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('urgent', 'Khẩn cấp'),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Trạng thái'
    )

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Ưu tiên'
    )

    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
            'style': 'display: none;'  # Ẩn widget mặc định, dùng custom dropdown
        }),
        label='Phòng ban phụ trách'
    )

    required_departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
            'style': 'display: none;'  # Ẩn widget mặc định, dùng custom dropdown
        }),
        label='Phòng ban bắt buộc tham gia'
    )

    class Meta:
        model = Project
        fields = ['name', 'description', 'client', 'status', 'priority', 
                  'start_date', 'end_date', 'estimated_budget', 'budget_for_personnel',
                  'estimated_employees', 'departments', 'required_departments']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tên dự án'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Mô tả dự án'
            }),
            'client': forms.Select(attrs={
                'class': 'form-select'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'estimated_budget': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'style': 'min-width: 150px; padding-right: 60px;'
            }),
            'budget_for_personnel': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'style': 'min-width: 150px; padding-right: 60px;',
                'placeholder': 'Ngân sách nhân sự'
            }),
            'estimated_employees': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Số nhân sự dự kiến'
            }),
        }
        labels = {
            'name': 'Tên dự án',
            'description': 'Mô tả',
            'client': 'Khách hàng',
            'start_date': 'Ngày bắt đầu',
            'end_date': 'Ngày kết thúc',
            'estimated_budget': 'Ngân sách dự kiến',
            'budget_for_personnel': 'Ngân sách nhân sự',
            'estimated_employees': 'Số nhân sự dự kiến',
        }


class TaskForm(forms.ModelForm):
    STATUS_CHOICES = [
        ('todo', 'Cần làm'),
        ('in_progress', 'Đang thực hiện'),
        ('review', 'Đang xem xét'),
        ('done', 'Hoàn thành'),
    ]

    ASSIGNMENT_STATUS_CHOICES = [
        ('assigned', 'Đã giao'),
        ('accepted', 'Đã nhận'),
        ('in_progress', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('rejected', 'Từ chối'),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Trạng thái'
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_department'
        }),
        label='Phòng ban phụ trách'
    )

    assignment_status = forms.ChoiceField(
        choices=ASSIGNMENT_STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Trạng thái giao/nhận',
        required=False
    )

    estimated_hours = forms.CharField(
        required=False,
        label='Giờ ước tính',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 7:30, 10:00h, 30p, 90p'
        }),
        help_text='Hỗ trợ: hh:mm (7:30), giờ (2.5), phút (30p/30m).'
    )

    class Meta:
        model = Task
        fields = ['project', 'name', 'description', 'status', 'department', 
                  'assigned_to', 'assignment_status', 'due_date', 'estimated_hours']
        widgets = {
            'project': forms.Select(attrs={
                'class': 'form-select'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tên công việc'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Mô tả công việc'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_assigned_to'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }
        labels = {
            'project': 'Dự án',
            'name': 'Tên công việc',
            'description': 'Mô tả',
            'assigned_to': 'Nhân viên thực hiện',
            'due_date': 'Hạn chót',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hiển thị dạng hh:mm cho instance nếu có
        try:
            val = getattr(self.instance, 'estimated_hours', None)
            if val is not None and Decimal(val) > 0:
                minutes = int((Decimal(val) * 60).quantize(Decimal('1')))
                h = minutes // 60
                m = minutes % 60
                self.initial['estimated_hours'] = f"{h}:{m:02d}"
        except Exception:
            pass

    def clean_estimated_hours(self):
        raw = (self.cleaned_data.get('estimated_hours') or '').strip().lower()
        if not raw:
            return Decimal('0')

        s = raw.replace(' ', '')
        # Chuẩn hoá hậu tố
        if s.endswith('h'):
            s = s[:-1]
        if s.endswith('giờ') or s.endswith('gio'):
            s = s.replace('giờ', '').replace('gio', '')

        # Định dạng hh:mm
        if ':' in s:
            parts = s.split(':', 1)
            if len(parts) != 2:
                raise forms.ValidationError('Giờ ước tính không hợp lệ. Ví dụ đúng: 7:30')
            try:
                h = int(parts[0] or '0')
                m = int(parts[1] or '0')
            except ValueError:
                raise forms.ValidationError('Giờ ước tính không hợp lệ. Ví dụ đúng: 7:30')
            if h < 0 or m < 0 or m >= 60:
                raise forms.ValidationError('Phút phải nằm trong khoảng 0-59.')
            return (Decimal(h) + (Decimal(m) / Decimal(60))).quantize(Decimal('0.01'))

        # Định dạng phút: 30p / 30m / 30phut
        is_minutes = False
        if s.endswith('p') or s.endswith('m'):
            is_minutes = True
            s = s[:-1]
        if s.endswith('phut'):
            is_minutes = True
            s = s[:-4]

        try:
            num = Decimal(s)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Giờ ước tính không hợp lệ. Ví dụ: 7:30, 2.5, 30p')

        if num < 0:
            raise forms.ValidationError('Giờ ước tính phải >= 0.')

        # Heuristic: số nguyên lớn (vd 30) mặc định hiểu là phút
        if not is_minutes and num == num.to_integral_value() and num > 12:
            is_minutes = True

        if is_minutes:
            return (num / Decimal(60)).quantize(Decimal('0.01'))

        # Mặc định: giờ (có thể là số thập phân)
        return num.quantize(Decimal('0.01'))


class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ['task', 'date', 'hours', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25', 'min': '0.1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        # Lấy employee và tasks từ kwargs
        employee = kwargs.pop('employee', None)
        tasks = kwargs.pop('tasks', None)
        
        super().__init__(*args, **kwargs)
        
        # Chỉ cho phép chọn tasks được gán cho nhân viên
        if tasks is not None:
            self.fields['task'] = forms.ModelChoiceField(
                queryset=tasks,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Công việc',
                required=True
            )
        else:
            # Nếu không có tasks, ẩn field này
            if 'task' in self.fields:
                del self.fields['task']
        
        # Ẩn employee field (tự động set từ user)
        if 'employee' in self.fields:
            del self.fields['employee']
        
        # Cập nhật labels
        self.fields['date'].label = 'Ngày làm việc'
        self.fields['hours'].label = 'Số giờ'
        self.fields['description'].label = 'Mô tả công việc (tùy chọn)'