from django import forms
from decimal import Decimal, InvalidOperation
from django.db.models import Q
from django.utils import timezone
from .models import Project, Task, TimeEntry, ProjectPhase, TaskProgressLog
from resources.models import Department, Employee, ResourceAllocation
from .delay_kpi_service import DelayKPIService


class ProjectForm(forms.ModelForm):
    # Override choices vá»›i tiáº¿ng Viá»‡t
    STATUS_CHOICES = [
        ('planning', 'LÃªn káº¿ hoáº¡ch'),
        ('active', 'Äang cháº¡y'),
        ('on_hold', 'Táº¡m dá»«ng'),
        ('completed', 'HoÃ n thÃ nh'),
        ('cancelled', 'ÄÃ£ há»§y'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Tháº¥p'),
        ('medium', 'Trung bÃ¬nh'),
        ('high', 'Cao'),
        ('urgent', 'Kháº©n cáº¥p'),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Tráº¡ng thÃ¡i'
    )

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Æ¯u tiÃªn'
    )

    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
            'style': 'display: none;'  # áº¨n widget máº·c Ä‘á»‹nh, dÃ¹ng custom dropdown
        }),
        label='PhÃ²ng ban phá»¥ trÃ¡ch'
    )

    required_departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
            'style': 'display: none;'  # áº¨n widget máº·c Ä‘á»‹nh, dÃ¹ng custom dropdown
        }),
        label='PhÃ²ng ban báº¯t buá»™c tham gia'
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
                'placeholder': 'TÃªn dá»± Ã¡n'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'MÃ´ táº£ dá»± Ã¡n'
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
                'placeholder': 'NgÃ¢n sÃ¡ch nhÃ¢n sá»±'
            }),
            'estimated_employees': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Sá»‘ nhÃ¢n sá»± dá»± kiáº¿n'
            }),
        }
        labels = {
            'name': 'TÃªn dá»± Ã¡n',
            'description': 'Mo ta',
            'client': 'KhÃ¡ch hÃ ng',
            'start_date': 'NgÃ y báº¯t Ä‘áº§u',
            'end_date': 'NgÃ y káº¿t thÃºc',
            'estimated_budget': 'NgÃ¢n sÃ¡ch dá»± kiáº¿n',
            'budget_for_personnel': 'NgÃ¢n sÃ¡ch nhÃ¢n sá»±',
            'estimated_employees': 'Sá»‘ nhÃ¢n sá»± dá»± kiáº¿n',
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
                f'Sá»‘ nhÃ¢n sá»± dá»± kiáº¿n khÃ´ng Ä‘Æ°á»£c vÆ°á»£t quÃ¡ nhÃ¢n sá»± hiá»‡n cÃ³ trong há»‡ thá»‘ng.'
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
                'placeholder': 'TÃªn giai Ä‘oáº¡n (VD: Requirement Analysis)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'MÃ´ táº£ giai Ä‘oáº¡n'
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
            'phase_name': 'TÃªn giai Ä‘oáº¡n',
            'description': 'Mo ta',
            'start_date': 'NgÃ y báº¯t Ä‘áº§u',
            'end_date': 'NgÃ y káº¿t thÃºc',
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
            if curr_start != expected_start:
                self.add_error('start_date', 'Cac giai doan phai lien tiep, khong duoc chong cheo hoac cach quang.')
                break
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
        ('assigned', 'ÄÃ£ giao'),
        ('accepted', 'ÄÃ£ nháº­n'),
        ('in_progress', 'Äang thá»±c hiá»‡n'),
        ('completed', 'HoÃ n thÃ nh'),
        ('rejected', 'Tá»« chá»‘i'),
    ]

    phase = forms.ModelChoiceField(
        queryset=ProjectPhase.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Giai Ä‘oáº¡n dá»± Ã¡n'
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
        label='Tiáº¿n Ä‘á»™ hoÃ n thÃ nh (%)'
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Tráº¡ng thÃ¡i'
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_department'
        }),
        label='PhÃ²ng ban phá»¥ trÃ¡ch'
    )

    assignment_status = forms.ChoiceField(
        choices=ASSIGNMENT_STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Tráº¡ng thÃ¡i giao/nháº­n',
        required=False
    )

    estimated_hours = forms.CharField(
        required=False,
        label='Giá» Æ°á»›c tÃ­nh',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'VÃ­ dá»¥: 7:30, 10:00h, 30p, 90p'
        }),
        help_text='Há»— trá»£: hh:mm (7:30), giá» (2.5), phÃºt (30p/30m).'
    )

    class Meta:
        model = Task
        fields = ['project', 'phase', 'name', 'description', 'status', 'progress_percent', 'department', 
                  'assigned_to', 'assignment_status', 'due_date', 'estimated_hours', 'required_skills', 'delay_reason_type', 'approved_delay', 'delay_explanation']
        widgets = {
            'project': forms.Select(attrs={
                'class': 'form-select'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'TÃªn cÃ´ng viá»‡c'
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
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }
        labels = {
            'project': 'Dá»± Ã¡n',
            'name': 'TÃªn cÃ´ng viá»‡c',
            'description': 'Mo ta',
            'required_skills': 'Ky nang yeu cau',
            'assigned_to': 'NhÃ¢n viÃªn thá»±c hiá»‡n',
            'due_date': 'Háº¡n chÃ³t',
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)

        # Lá»c phases theo project
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
        self.fields['assigned_to'].queryset = assigned_to_qs.order_by('last_name', 'first_name')

        # Hiá»ƒn thá»‹ dáº¡ng hh:mm cho instance náº¿u cÃ³
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
        # Chuáº©n hoÃ¡ háº­u tá»‘
        if s.endswith('h'):
            s = s[:-1]
        if s.endswith('giá»') or s.endswith('gio'):
            s = s.replace('giá»', '').replace('gio', '')

        # Äá»‹nh dáº¡ng hh:mm
        if ':' in s:
            parts = s.split(':', 1)
            if len(parts) != 2:
                raise forms.ValidationError('Giá» Æ°á»›c tÃ­nh khÃ´ng há»£p lá»‡. VÃ­ dá»¥ Ä‘Ãºng: 7:30')
            try:
                h = int(parts[0] or '0')
                m = int(parts[1] or '0')
            except ValueError:
                raise forms.ValidationError('Giá» Æ°á»›c tÃ­nh khÃ´ng há»£p lá»‡. VÃ­ dá»¥ Ä‘Ãºng: 7:30')
            if h < 0 or m < 0 or m >= 60:
                raise forms.ValidationError('PhÃºt pháº£i náº±m trong khoáº£ng 0-59.')
            return (Decimal(h) + (Decimal(m) / Decimal(60))).quantize(Decimal('0.01'))

        # Äá»‹nh dáº¡ng phÃºt: 30p / 30m / 30phut
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
            raise forms.ValidationError('Giá» Æ°á»›c tÃ­nh khÃ´ng há»£p lá»‡. VÃ­ dá»¥: 7:30, 2.5, 30p')

        if num < 0:
            raise forms.ValidationError('Giá» Æ°á»›c tÃ­nh pháº£i >= 0.')

        # Heuristic: sá»‘ nguyÃªn lá»›n (vd 30) máº·c Ä‘á»‹nh hiá»ƒu lÃ  phÃºt
        if not is_minutes and num == num.to_integral_value() and num > 12:
            is_minutes = True

        if is_minutes:
            return (num / Decimal(60)).quantize(Decimal('0.01'))

        # Máº·c Ä‘á»‹nh: giá» (cÃ³ thá»ƒ lÃ  sá»‘ tháº­p phÃ¢n)
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
                self.add_error('name', 'TÃªn cÃ´ng viá»‡c Ä‘Ã£ tá»“n táº¡i trong dá»± Ã¡n nÃ y. Vui lÃ²ng Ä‘áº·t tÃªn khÃ¡c')


        due_date = cleaned_data.get('due_date')
        status = cleaned_data.get('status')
        delay_explanation = (cleaned_data.get('delay_explanation') or '').strip()
        if due_date and status == 'done':
            days_late = max((timezone.now().date() - due_date).days, 0)
            cfg = DelayKPIService.get_active_config()
            if days_late > int(cfg.requires_explanation_after_days) and not delay_explanation:
                self.add_error('delay_explanation', 'Task tre han qua nguong, vui long nhap giai trinh.')
        return cleaned_data


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
            'employee': 'NhÃ¢n sá»±',
            'allocation_percentage': 'Tá»· lá»‡ phÃ¢n bá»• (%)',
            'start_date': 'NgÃ y báº¯t Ä‘áº§u',
            'end_date': 'NgÃ y káº¿t thÃºc',
            'notes': 'Ghi chÃº',
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
        # Láº¥y employee vÃ  tasks tá»« kwargs
        employee = kwargs.pop('employee', None)
        tasks = kwargs.pop('tasks', None)
        
        super().__init__(*args, **kwargs)
        
        # Chá»‰ cho phÃ©p chá»n tasks Ä‘Æ°á»£c gÃ¡n cho nhÃ¢n viÃªn
        if tasks is not None:
            self.fields['task'] = forms.ModelChoiceField(
                queryset=tasks,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='CÃ´ng viá»‡c',
                required=True
            )
        else:
            # Náº¿u khÃ´ng cÃ³ tasks, áº©n field nÃ y
            if 'task' in self.fields:
                del self.fields['task']
        
        # áº¨n employee field (tá»± Ä‘á»™ng set tá»« user)
        if 'employee' in self.fields:
            del self.fields['employee']
        
        # Cáº­p nháº­t labels
        self.fields['date'].label = 'NgÃ y lÃ m viá»‡c'
        self.fields['hours'].label = 'Sá»‘ giá»'
        self.fields['description'].label = 'MÃ´ táº£ cÃ´ng viá»‡c (tÃ¹y chá»n)'





