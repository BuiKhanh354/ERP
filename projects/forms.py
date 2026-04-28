from django import forms
from decimal import Decimal, InvalidOperation
from django.db.models import Q
from django.utils import timezone
from .models import Project, Task, TimeEntry, ProjectPhase, TaskProgressLog
from resources.models import Department, Employee, ResourceAllocation
from .delay_kpi_service import DelayKPIService


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

    confirm_add_employees = forms.BooleanField(
        required=False,
        label='Xac nhan them nhan vien tu dong dua vao phong ban da chon',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Chi xac nhan khi nhan vien co cong viec phu hop trong du an.'
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
            'description': 'Mo ta',
            'client': 'Khách hàng',
            'start_date': 'Ngày bắt đầu',
            'end_date': 'Ngày kết thúc',
            'estimated_budget': 'Ngân sách dự kiến',
            'budget_for_personnel': 'Ngân sách nhân sự',
            'estimated_employees': 'Số nhân sự dự kiến',
        }

    def clean(self):
        cleaned_data = super().clean()
        departments = cleaned_data.get('departments')
        required_departments = cleaned_data.get('required_departments')

        if required_departments:
            selected_departments = departments or []
            missing = [d for d in required_departments if d not in selected_departments]
            if missing:
                self.add_error(
                    'required_departments',
                    'Phong ban bat buoc phai nam trong danh sach phong ban phu trach.'
                )
        return cleaned_data

    def clean_estimated_employees(self):
        estimated = self.cleaned_data.get('estimated_employees')
        if estimated is None:
            return estimated

        max_available = Employee.objects.filter(is_active=True).count()
        if estimated > max_available:
            raise forms.ValidationError(
                f'Số nhân sự dự kiến không được vượt quá nhân sự hiện có trong hệ thống.'
            )
        return estimated



class PhaseForm(forms.ModelForm):
    """Form cho tao/sua giai doan du an."""

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
    class Meta:
        model = ProjectPhase
        fields = ['phase_name', 'description', 'start_date', 'end_date']
        widgets = {
            'phase_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tên giai đoạn (VD: Requirement Analysis)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Mô tả giai đoạn'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }
        labels = {
            'phase_name': 'Tên giai đoạn',
            'description': 'Mo ta',
            'start_date': 'Ngày bắt đầu',
            'end_date': 'Ngày kết thúc',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'Ngay ket thuc phai lon hon ngay bat dau.')
            return cleaned_data

        project = self.project or getattr(self.instance, 'project', None)
        if not project:
            return cleaned_data

        if not project.start_date:
            self.add_error('start_date', 'Du an chua co ngay bat dau, vui long cap nhat ngay bat dau du an truoc.')
            return cleaned_data

        phases = list(project.phases.order_by('order_index', 'created_at'))
        instance_id = self.instance.pk if self.instance and self.instance.pk else None
        if instance_id:
            phases = [p for p in phases if p.pk != instance_id]

        # Build ordered list with current phase inserted at its order
        current_order = getattr(self.instance, 'order_index', None)
        if current_order is None:
            # new phase goes last
            phases.append(self.instance)
        else:
            inserted = False
            for idx, phase in enumerate(phases):
                if phase.order_index >= current_order:
                    phases.insert(idx, self.instance)
                    inserted = True
                    break
            if not inserted:
                phases.append(self.instance)

        # Map proposed dates
        date_map = {}
        for phase in phases:
            if phase.pk == instance_id:
                date_map[phase.pk] = (start_date, end_date)
            else:
                date_map[phase.pk] = (phase.start_date, phase.end_date)

        # Validate first phase start date
        if phases:
            first_phase = phases[0]
            first_start = date_map[first_phase.pk][0]
            if not first_start:
                self.add_error('start_date', 'Phai khai bao ngay bat dau cho giai doan dau tien.')
                return cleaned_data
            if first_start != project.start_date:
                self.add_error('start_date', 'Giai doan dau tien phai trung voi ngay bat dau cua du an.')
                return cleaned_data

        # Validate continuity
        from datetime import timedelta
        for idx in range(1, len(phases)):
            prev_phase = phases[idx - 1]
            curr_phase = phases[idx]
            prev_end = date_map[prev_phase.pk][1]
            curr_start = date_map[curr_phase.pk][0]
            if not prev_end or not curr_start:
                self.add_error('start_date', 'Can khai bao ngay bat dau/ket thuc day du de dam bao cac giai doan lien tiep.')
                break
            expected_start = prev_end + timedelta(days=1)
            # if curr_start != expected_start:
            #     self.add_error('start_date', 'Cac giai doan phai lien tiep, khong duoc chong cheo hoac cach quang.')
            #     break
        return cleaned_data


class TaskForm(forms.ModelForm):
    STATUS_CHOICES = [
        ('todo', 'Can lam'),
        ('in_progress', 'Dang thuc hien'),
        ('review', 'Dang xem xet'),
        ('done', 'Hoan thanh'),
        ('cancelled', 'Da huy'),
    ]

    ASSIGNMENT_STATUS_CHOICES = [
        ('assigned', 'Đã giao'),
        ('accepted', 'Đã nhận'),
        ('in_progress', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('rejected', 'Từ chối'),
    ]

    phase = forms.ModelChoiceField(
        queryset=ProjectPhase.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Giai đoạn dự án'
    )

    progress_percent = forms.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'type': 'range',
            'min': '0',
            'max': '100',
            'step': '5',
        }),
        label='Tiến độ hoàn thành (%)'
    )

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

    assignees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'id': 'id_assignees',
            'size': '6',
        }),
        label='Nhân viên thực hiện (nhiều người)'
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
        fields = ['project', 'phase', 'name', 'description', 'status', 'progress_percent', 'department',
                  'assignees', 'assigned_to', 'assignment_status', 'planned_start_date', 'due_date', 'estimated_hours', 'required_skills', 'delay_reason_type', 'approved_delay', 'delay_explanation']
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
                'placeholder': 'Mo ta cong viec'
            }),
            'required_skills': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Vi du: Python, Django, SQL'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_assigned_to'
            }),
            'planned_start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }
        labels = {
            'project': 'Dự án',
            'name': 'Tên công việc',
            'description': 'Mo ta',
            'required_skills': 'Ky nang yeu cau',
            'assignees': 'Nhân viên thực hiện (nhiều người)',
            'assigned_to': 'Nhân viên thực hiện',
            'planned_start_date': 'Ngay bat dau du kien',
            'due_date': 'Hạn chót',
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)

        # Lọc phases theo project
        if project:
            self.fields['project'].initial = project
            self.fields['phase'].queryset = ProjectPhase.objects.filter(project=project)
        elif self.instance and self.instance.pk and self.instance.project_id:
            self.fields['phase'].queryset = ProjectPhase.objects.filter(project=self.instance.project)
            project = self.instance.project

        # Chi cho phep giao task cho nhan su da duoc phan bo vao du an.
        assigned_to_qs = Employee.objects.filter(is_active=True)
        if project:
            allocated_ids = ResourceAllocation.objects.filter(
                project=project
            ).values_list('employee_id', flat=True).distinct()
            assigned_to_qs = Employee.objects.filter(id__in=allocated_ids, is_active=True)
            # Khi sua task, van hien thi nguoi dang duoc giao (neu co) de tranh mat lua chon hien tai.
            current_assignee_id = getattr(self.instance, 'assigned_to_id', None)
            if current_assignee_id and not assigned_to_qs.filter(id=current_assignee_id).exists():
                assigned_to_qs = Employee.objects.filter(
                    Q(id__in=allocated_ids) | Q(id=current_assignee_id),
                    is_active=True
                ).distinct()
        assignee_qs = assigned_to_qs.order_by('last_name', 'first_name')
        self.fields['assigned_to'].queryset = assignee_qs
        self.fields['assignees'].queryset = assignee_qs

        # Initial multiple assignees when editing existing task.
        if self.instance and self.instance.pk:
            existing_ids = list(self.instance.assignees.values_list('id', flat=True))
            if not existing_ids and self.instance.assigned_to_id:
                existing_ids = [self.instance.assigned_to_id]
            self.initial['assignees'] = existing_ids

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


    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get('project') or getattr(self.instance, 'project', None)
        task_name = (cleaned_data.get('name') or '').strip()

        if task_name:
            cleaned_data['name'] = task_name

        if project and task_name:
            duplicate_qs = Task.objects.filter(
                project=project,
                name__iexact=task_name
            )
            if self.instance and self.instance.pk:
                duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)

            if duplicate_qs.exists():
                self.add_error('name', 'Tên công việc đã tồn tại trong dự án này. Vui lòng đặt tên khác')


        due_date = cleaned_data.get('due_date')
        planned_start_date = cleaned_data.get('planned_start_date')
        phase = cleaned_data.get('phase')
        status = cleaned_data.get('status')
        delay_explanation = (cleaned_data.get('delay_explanation') or '').strip()

        if planned_start_date and due_date and planned_start_date > due_date:
            self.add_error('planned_start_date', 'Ngay bat dau du kien phai nho hon hoac bang han chot.')

        if phase:
            if phase.start_date and planned_start_date and planned_start_date < phase.start_date:
                self.add_error('planned_start_date', 'Ngay bat dau task phai nam trong khoang ngay cua giai doan.')
            if phase.end_date and due_date and due_date > phase.end_date:
                self.add_error('due_date', 'Han chot task phai nam trong khoang ngay cua giai doan.')
            if phase.start_date and due_date and due_date < phase.start_date:
                self.add_error('due_date', 'Han chot task khong duoc truoc ngay bat dau giai doan.')
            if phase.end_date and planned_start_date and planned_start_date > phase.end_date:
                self.add_error('planned_start_date', 'Ngay bat dau task khong duoc sau ngay ket thuc giai doan.')
        if due_date and status == 'done':
            days_late = max((timezone.now().date() - due_date).days, 0)
            cfg = DelayKPIService.get_active_config()
            if days_late > int(cfg.requires_explanation_after_days) and not delay_explanation:
                self.add_error('delay_explanation', 'Task tre han qua nguong, vui long nhap giai trinh.')

        assignees = list(cleaned_data.get('assignees') or [])
        assigned_to = cleaned_data.get('assigned_to')
        if assigned_to and assigned_to not in assignees:
            assignees.insert(0, assigned_to)
        if assignees:
            cleaned_data['assignees'] = assignees
            cleaned_data['assigned_to'] = assignees[0]
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        assignees = list(self.cleaned_data.get('assignees') or [])
        if assignees:
            instance.assigned_to = assignees[0]
        elif self.cleaned_data.get('assigned_to'):
            instance.assigned_to = self.cleaned_data.get('assigned_to')
            assignees = [instance.assigned_to]
        else:
            instance.assigned_to = None

        if commit:
            instance.save()
            instance.assignees.set(assignees)
            self.save_m2m()
        else:
            self._pending_assignee_ids = [a.id for a in assignees]
        return instance


class ProjectPersonnelAllocationForm(forms.ModelForm):
    """Form them nhan su vao mot du an cu the."""

    class Meta:
        model = ResourceAllocation
        fields = ['employee', 'allocation_percentage', 'start_date', 'end_date', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'allocation_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01'
            }),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'employee': 'Nhân sự',
            'allocation_percentage': 'Tỷ lệ phân bổ (%)',
            'start_date': 'Ngày bắt đầu',
            'end_date': 'Ngày kết thúc',
            'notes': 'Ghi chú',
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)

        employees = Employee.objects.filter(is_active=True).select_related('department')
        if self.project:
            department_ids = list(self.project.departments.values_list('id', flat=True))
            if department_ids:
                employees = employees.filter(department_id__in=department_ids)

            if not self.instance.pk:
                self.initial['start_date'] = self.project.start_date
                self.initial['end_date'] = self.project.end_date

        self.fields['employee'].queryset = employees.order_by('last_name', 'first_name')

    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get('employee')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'Ngay ket thuc phai lon hon hoac bang ngay bat dau.')

        if self.project and employee and start_date:
            exists = ResourceAllocation.objects.filter(
                project=self.project,
                employee=employee,
                start_date=start_date
            ).exists()
            if exists:
                self.add_error('employee', 'Nhan su nay da duoc them vao du an voi ngay bat dau nay.')

        return cleaned_data


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





