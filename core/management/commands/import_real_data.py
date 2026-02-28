"""
Management command để import data thực và gán cho 2 user chính.
Chạy: python manage.py import_real_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from projects.models import Project, Task, TimeEntry, PersonnelRecommendation, PersonnelRecommendationDetail
from resources.models import Employee, Department, Position, EmployeeHourlyRate, ResourceAllocation
from budgeting.models import Budget, Expense, BudgetCategory
from clients.models import Client
from performance.models import PerformanceScore
from core.models import Notification
from core.notification_service import NotificationService


class Command(BaseCommand):
    help = 'Import data thực và gán cho 2 user chính (quản lý và nhân viên)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Xác nhận import data (bắt buộc)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '[WARNING] CANH BAO: Lenh nay se import data thuc vao database!\n'
                    'De xac nhan, chay: python manage.py import_real_data --confirm'
                )
            )
            return

        self.stdout.write(self.style.SUCCESS('Dang import data thuc...'))

        # Lấy hoặc tạo 2 user chính
        try:
            manager_user = User.objects.get(email='thanhhung111120021@gmail.com')
            self.stdout.write(f'[OK] Tim thay user quan ly: {manager_user.username} ({manager_user.email})')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('[ERROR] Khong tim thay user quan ly: thanhhung111120021@gmail.com'))
            return

        try:
            employee_user = User.objects.get(email='nthung.viettin@gmail.com')
            self.stdout.write(f'[OK] Tim thay user nhan vien: {employee_user.username} ({employee_user.email})')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('[ERROR] Khong tim thay user nhan vien: nthung.viettin@gmail.com'))
            return

        # Đảm bảo roles đúng
        if hasattr(manager_user, 'profile'):
            manager_user.profile.role = 'manager'
            manager_user.profile.save()
            self.stdout.write('[OK] Da set role quan ly cho manager_user')

        if hasattr(employee_user, 'profile'):
            employee_user.profile.role = 'employee'
            employee_user.profile.save()
            self.stdout.write('[OK] Da set role nhan vien cho employee_user')

        created_counts = {}

        # 1. Tạo Phòng ban
        self.stdout.write('\n[INFO] Dang tao Phong ban...')
        dept_it, _ = Department.objects.get_or_create(
            name='Phòng Công nghệ Thông tin',
            defaults={
                'description': 'Phòng ban phụ trách phát triển phần mềm và công nghệ',
                'created_by': manager_user,
            }
        )
        dept_marketing, _ = Department.objects.get_or_create(
            name='Phòng Marketing',
            defaults={
                'description': 'Phòng ban phụ trách marketing và truyền thông',
                'created_by': manager_user,
            }
        )
        dept_sales, _ = Department.objects.get_or_create(
            name='Phòng Kinh doanh',
            defaults={
                'description': 'Phòng ban phụ trách bán hàng và chăm sóc khách hàng',
                'created_by': manager_user,
            }
        )
        dept_hr, _ = Department.objects.get_or_create(
            name='Phòng Nhân sự',
            defaults={
                'description': 'Phòng ban phụ trách quản lý nhân sự',
                'created_by': manager_user,
            }
        )
        created_counts['Department'] = 4
        self.stdout.write(f'   [OK] Da tao 4 phong ban')

        # 2. Tạo Chức vụ
        self.stdout.write('\n[INFO] Dang tao Chuc vu...')
        position_dev, _ = Position.objects.get_or_create(
            name='Lập trình viên',
            defaults={
                'description': 'Phát triển phần mềm và ứng dụng',
                'is_active': True,
            }
        )
        position_senior_dev, _ = Position.objects.get_or_create(
            name='Lập trình viên Senior',
            defaults={
                'description': 'Lập trình viên cấp cao',
                'is_active': True,
            }
        )
        position_manager, _ = Position.objects.get_or_create(
            name='Quản lý Dự án',
            defaults={
                'description': 'Quản lý và điều phối dự án',
                'is_active': True,
            }
        )
        position_marketing, _ = Position.objects.get_or_create(
            name='Chuyên viên Marketing',
            defaults={
                'description': 'Thực hiện các hoạt động marketing',
                'is_active': True,
            }
        )
        position_sales, _ = Position.objects.get_or_create(
            name='Nhân viên Kinh doanh',
            defaults={
                'description': 'Bán hàng và chăm sóc khách hàng',
                'is_active': True,
            }
        )
        position_hr, _ = Position.objects.get_or_create(
            name='Chuyên viên Nhân sự',
            defaults={
                'description': 'Quản lý nhân sự và tuyển dụng',
                'is_active': True,
            }
        )
        created_counts['Position'] = 6
        self.stdout.write(f'   [OK] Da tao 6 chuc vu')

        # 3. Tạo Nhân viên (7 người)
        self.stdout.write('\n[INFO] Dang tao Nhan vien...')
        employees = []
        
        # Nhân viên 1 - gán cho employee_user
        employee1, created = Employee.objects.get_or_create(
            email=employee_user.email,
            defaults={
                'employee_id': 'EMP001',
                'first_name': employee_user.first_name or 'Nhân',
                'last_name': employee_user.last_name or 'Viên',
                'phone': '0901234567',
                'department': dept_it,
                'position': position_dev.name,
                'position_fk': position_dev,
                'employment_type': 'full_time',
                'hire_date': timezone.now().date() - timedelta(days=365),
                'is_active': True,
                'created_by': manager_user,
            }
        )
        if not created:
            employee1.user = employee_user
            employee1.department = dept_it
            employee1.position_fk = position_dev
            employee1.save()
        else:
            employee1.user = employee_user
            employee1.save()
        employees.append(employee1)
        self.stdout.write(f'   [OK] Da tao/cap nhat nhan vien: {employee1.email}')

        # Nhân viên 2-7
        employee_data = [
            ('EMP002', 'Minh', 'Nguyễn', 'dev2@example.com', '0901234568', dept_it, position_dev, 180),
            ('EMP003', 'Lan', 'Trần', 'marketing1@example.com', '0901234569', dept_marketing, position_marketing, 90),
            ('EMP004', 'Hùng', 'Lê', 'dev3@example.com', '0901234570', dept_it, position_senior_dev, 540),
            ('EMP005', 'Hoa', 'Phạm', 'sales1@example.com', '0901234571', dept_sales, position_sales, 120),
            ('EMP006', 'Tuấn', 'Hoàng', 'dev4@example.com', '0901234572', dept_it, position_dev, 60),
            ('EMP007', 'Mai', 'Võ', 'hr1@example.com', '0901234573', dept_hr, position_hr, 200),
        ]

        for emp_id, first_name, last_name, email, phone, dept, pos, days_ago in employee_data:
            emp, created = Employee.objects.get_or_create(
                email=email,
                defaults={
                    'employee_id': emp_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone,
                    'department': dept,
                    'position': pos.name,
                    'position_fk': pos,
                    'employment_type': 'full_time',
                    'hire_date': timezone.now().date() - timedelta(days=days_ago),
                    'is_active': True,
                    'created_by': manager_user,
                }
            )
            if created:
                self.stdout.write(f'   [OK] Da tao nhan vien: {emp.email}')
            employees.append(emp)

        created_counts['Employee'] = len(employees)

        # 4. Tạo Lương/Giờ cho nhân viên
        self.stdout.write('\n[INFO] Dang tao Luong/Gio...')
        now = timezone.now()
        salary_ranges = [
            (Decimal('15000000'), Decimal('176')),  # 15M - nhân viên chính
            (Decimal('12000000'), Decimal('176')),  # 12M - nhân viên thường
            (Decimal('20000000'), Decimal('176')),  # 20M - senior
            (Decimal('10000000'), Decimal('176')),  # 10M - junior
        ]
        
        hourly_rate_count = 0
        for idx, emp in enumerate(employees):
            # Chọn mức lương dựa trên vị trí
            if 'Senior' in emp.position:
                monthly_salary, working_hours = salary_ranges[2]
            elif emp == employee1:
                monthly_salary, working_hours = salary_ranges[0]
            elif idx < 3:
                monthly_salary, working_hours = salary_ranges[1]
            else:
                monthly_salary, working_hours = salary_ranges[3]
            
            hourly_rate = monthly_salary / working_hours
            
            # Cập nhật hourly_rate cho employee
            emp.hourly_rate = hourly_rate
            emp.save()
            
            # Tạo lương/giờ cho 6 tháng gần nhất
            for i in range(6):
                month_date = now - timedelta(days=30 * i)
                
                rate, created = EmployeeHourlyRate.objects.get_or_create(
                    employee=emp,
                    month=month_date.month,
                    year=month_date.year,
                    defaults={
                        'monthly_salary': monthly_salary,
                        'working_hours_per_month': working_hours,
                        'hourly_rate': hourly_rate,
                        'notes': f'Luong thang {month_date.month}/{month_date.year}',
                        'created_by': manager_user,
                    }
                )
                if created:
                    hourly_rate_count += 1
        
        created_counts['EmployeeHourlyRate'] = hourly_rate_count
        self.stdout.write(f'   [OK] Da tao {hourly_rate_count} ban ghi luong/gio (6 thang x {len(employees)} nhan vien)')

        # 5. Tạo Khách hàng (5 khách hàng)
        self.stdout.write('\n[INFO] Dang tao Khach hang...')
        clients = []
        client_data = [
            ('Công ty ABC', 'client1@example.com', '0281234567', '123 Đường ABC, Quận 1, TP.HCM'),
            ('Công ty XYZ', 'client2@example.com', '0281234568', '456 Đường XYZ, Quận 3, TP.HCM'),
            ('Công ty DEF', 'client3@example.com', '0281234569', '789 Đường DEF, Quận 7, TP.HCM'),
            ('Công ty GHI', 'client4@example.com', '0281234570', '321 Đường GHI, Quận 2, TP.HCM'),
            ('Công ty JKL', 'client5@example.com', '0281234571', '654 Đường JKL, Quận 5, TP.HCM'),
        ]

        for name, email, phone, address in client_data:
            client, created = Client.objects.get_or_create(
                email=email,
                defaults={
                    'name': name,
                    'phone': phone,
                    'address': address,
                    'client_type': 'corporate',
                    'status': 'active',
                    'created_by': manager_user,
                }
            )
            if created:
                self.stdout.write(f'   [OK] Da tao khach hang: {name}')
            clients.append(client)

        created_counts['Client'] = len(clients)

        # 6. Tạo Dự án (6 dự án)
        self.stdout.write('\n[INFO] Dang tao Du an...')
        projects = []
        project_data = [
            ('Dự án Phát triển Website ERP', 'Phát triển hệ thống ERP quản lý dự án và nhân sự', clients[0], 'active', 'high', 60, 120, Decimal('500000000'), Decimal('200000000'), 5, [dept_it]),
            ('Dự án Marketing Campaign Q1', 'Chiến dịch marketing quý 1 năm 2026', clients[1], 'active', 'medium', 30, 60, Decimal('300000000'), Decimal('100000000'), 3, [dept_marketing]),
            ('Dự án Mobile App Development', 'Phát triển ứng dụng di động cho khách hàng', clients[2], 'active', 'high', 90, 180, Decimal('800000000'), Decimal('350000000'), 6, [dept_it]),
            ('Dự án E-commerce Platform', 'Xây dựng nền tảng thương mại điện tử', clients[0], 'planning', 'high', 0, 240, Decimal('1000000000'), Decimal('450000000'), 8, [dept_it, dept_marketing]),
            ('Dự án Brand Identity Design', 'Thiết kế nhận diện thương hiệu', clients[3], 'active', 'medium', 15, 45, Decimal('150000000'), Decimal('50000000'), 2, [dept_marketing]),
            ('Dự án Sales Training Program', 'Chương trình đào tạo bán hàng', clients[4], 'active', 'low', 7, 30, Decimal('100000000'), Decimal('30000000'), 2, [dept_sales]),
        ]

        for name, desc, client, status, priority, days_start, days_end, est_budget, budget_personnel, est_emp, depts in project_data:
            start_date = timezone.now().date() - timedelta(days=days_start) if days_start > 0 else None
            end_date = timezone.now().date() + timedelta(days=days_end) if days_end > 0 else None
            
            project, created = Project.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'client': client,
                    'status': status,
                    'priority': priority,
                    'start_date': start_date,
                    'end_date': end_date,
                    'estimated_budget': est_budget,
                    'budget_for_personnel': budget_personnel,
                    'estimated_employees': est_emp,
                    'created_by': manager_user,
                }
            )
            if created:
                for dept in depts:
                    project.required_departments.add(dept)
                    project.departments.add(dept)
                self.stdout.write(f'   [OK] Da tao du an ID: {project.pk}')
            projects.append(project)

        created_counts['Project'] = len(projects)

        # 7. Tạo Resource Allocation
        self.stdout.write('\n[INFO] Dang tao Resource Allocation...')
        allocation_count = 0
        # Đảm bảo employee1 (user nhân viên) được phân bổ vào ít nhất 2-3 dự án IT
        it_projects = [p for p in projects[:4] if dept_it in p.departments.all() or not p.departments.exists()]
        for project in it_projects[:3]:
            # Phân bổ employee1 vào các dự án IT
            allocation, created = ResourceAllocation.objects.get_or_create(
                employee=employee1,
                project=project,
                start_date=project.start_date or timezone.now().date(),
                defaults={
                    'allocation_percentage': Decimal(str(random.randint(50, 80))),
                    'end_date': project.end_date,
                    'notes': f'Phan bo nhan su chinh cho du an {project.name}',
                    'created_by': manager_user,
                }
            )
            if created:
                allocation_count += 1
        
        # Phân bổ các nhân viên khác
        for project in projects[:4]:
            # Phân bổ 2-3 nhân viên khác cho mỗi dự án (tránh trùng với employee1 nếu đã có)
            other_employees = [e for e in employees if e != employee1]
            selected_employees = random.sample(other_employees, min(2, len(other_employees)))
            for emp in selected_employees:
                if emp.department in project.departments.all() or not project.departments.exists():
                    allocation, created = ResourceAllocation.objects.get_or_create(
                        employee=emp,
                        project=project,
                        start_date=project.start_date or timezone.now().date(),
                        defaults={
                            'allocation_percentage': Decimal(str(random.randint(30, 70))),
                            'end_date': project.end_date,
                            'notes': f'Phan bo nhan su cho du an {project.name}',
                            'created_by': manager_user,
                        }
                    )
                    if created:
                        allocation_count += 1
        
        created_counts['ResourceAllocation'] = allocation_count
        self.stdout.write(f'   [OK] Da tao {allocation_count} phan bo nhan su (employee1 duoc phan bo vao {len(it_projects[:3])} du an)')

        # 8. Tạo Budget Category
        self.stdout.write('\n[INFO] Dang tao Budget Category...')
        budget_category, _ = BudgetCategory.objects.get_or_create(
            name='Ngân sách chính',
            defaults={
                'description': 'Ngân sách chính cho dự án',
                'created_by': manager_user,
            }
        )
        created_counts['BudgetCategory'] = 1

        # 9. Tạo Ngân sách
        self.stdout.write('\n[INFO] Dang tao Ngan sach...')
        current_year = timezone.now().year
        budget_count = 0
        for project in projects:
            budget, created = Budget.objects.get_or_create(
                project=project,
                category=budget_category,
                fiscal_year=current_year,
                defaults={
                    'allocated_amount': project.estimated_budget,
                    'spent_amount': project.estimated_budget * Decimal('0.3'),  # Đã chi 30%
                    'created_by': manager_user,
                }
            )
            if created:
                budget_count += 1

        created_counts['Budget'] = budget_count
        self.stdout.write(f'   [OK] Da tao {budget_count} ngan sach')

        # 10. Tạo Chi phí
        self.stdout.write('\n[INFO] Dang tao Chi phi...')
        expense_count = 0
        expense_types = ['equipment', 'labor', 'material', 'travel', 'other']
        # Lấy employee_user nếu có
        try:
            employee_user = User.objects.get(email='nthung.viettin@gmail.com')
        except User.DoesNotExist:
            employee_user = manager_user
        
        for idx, project in enumerate(projects[:4]):
            # Tạo 2-3 chi phí cho mỗi dự án
            for i in range(random.randint(2, 3)):
                budget = Budget.objects.filter(project=project).first()
                if budget:
                    # Một số expenses được tạo bởi nhân viên (đặc biệt là các dự án mà nhân viên được phân bổ)
                    # Nếu project có employee1 được phân bổ, thì một số expenses sẽ do employee_user tạo
                    is_employee_project = ResourceAllocation.objects.filter(
                        employee=employee1,
                        project=project
                    ).exists()
                    
                    # 30% expenses của projects nhân viên được phân bổ sẽ do nhân viên tạo
                    # 70% expenses do quản lý tạo
                    creator = employee_user if (is_employee_project and random.random() < 0.3) else manager_user
                    
                    expense, created = Expense.objects.get_or_create(
                        project=project,
                        category=budget_category,
                        amount=project.estimated_budget * Decimal(str(random.uniform(0.05, 0.15))),
                        expense_date=timezone.now().date() - timedelta(days=random.randint(1, 60)),
                        defaults={
                            'budget': budget,
                            'description': f'Chi phi {expense_types[i % len(expense_types)]} cho du an {project.name}',
                            'expense_type': expense_types[i % len(expense_types)],
                            'created_by': creator,
                        }
                    )
                    if created:
                        expense_count += 1

        created_counts['Expense'] = expense_count
        self.stdout.write(f'   [OK] Da tao {expense_count} chi phi')

        # 10.1 Tạo một số Notification mẫu cho nhân viên (test bell + modal)
        try:
            allocated_proj = ResourceAllocation.objects.filter(employee=employee1).select_related('project').first()
            if allocated_proj and getattr(employee1, "user", None):
                NotificationService.notify(
                    user=employee1.user,
                    title=f"Bạn được thêm vào dự án: {allocated_proj.project.name}",
                    message=f"Bạn vừa được thêm vào dự án \"{allocated_proj.project.name}\".",
                    level=Notification.LEVEL_INFO,
                    url=f"/projects/{allocated_proj.project.pk}/",
                    actor=manager_user,
                    dedupe_minutes=0,
                )
        except Exception:
            pass

        # 11. Tạo Công việc (15 task)
        self.stdout.write('\n[INFO] Dang tao Cong viec...')
        task_statuses = ['todo', 'in_progress', 'done']
        task_count = 0
        task_names = [
            'Thiết kế Database Schema',
            'Phát triển Module Quản lý Dự án',
            'Thiết kế UI/UX',
            'Lập kế hoạch Marketing',
            'Code Backend API',
            'Code Frontend Components',
            'Viết Unit Tests',
            'Tích hợp Payment Gateway',
            'Tối ưu hóa Performance',
            'Deploy lên Production',
            'Viết Documentation',
            'Training cho khách hàng',
            'Bug Fixing',
            'Code Review',
            'Setup CI/CD Pipeline',
        ]

        # Đảm bảo employee1 được assign vào ít nhất 5-6 tasks từ các dự án IT
        it_projects = [p for p in projects[:4] if dept_it in p.departments.all() or not p.departments.exists()]
        employee1_task_count = 0
        for project in it_projects[:3]:
            # Assign 2 tasks cho employee1 từ mỗi dự án IT
            selected_tasks = random.sample(task_names, 2)
            for task_name in selected_tasks:
                status = random.choice(['in_progress', 'done'])
                days_ago = random.randint(1, 30)
                due_days = random.randint(5, 30)
                
                task, created = Task.objects.get_or_create(
                    project=project,
                    name=f'{task_name} - {project.name}',
                    defaults={
                        'description': f'{task_name} cho dự án {project.name}',
                        'status': status,
                        'department': dept_it,
                        'assigned_to': employee1,
                        'assignment_status': 'in_progress' if status == 'in_progress' else 'completed',
                        'due_date': timezone.now().date() + timedelta(days=due_days),
                        'estimated_hours': Decimal(str(random.randint(20, 80))),
                        'started_at': timezone.now() - timedelta(days=days_ago),
                        'created_by': manager_user,
                    }
                )
                if created:
                    task_count += 1
                    employee1_task_count += 1

        # Tạo tasks cho các nhân viên khác
        for project in projects[:4]:
            # Tạo 2-3 task cho mỗi dự án (tránh trùng với tasks đã tạo cho employee1)
            remaining_tasks = [t for t in task_names if not Task.objects.filter(project=project, name__contains=t).exists()]
            if remaining_tasks:
                selected_tasks = random.sample(remaining_tasks, min(2, len(remaining_tasks)))
                for task_name in selected_tasks:
                    # Chọn nhân viên phù hợp với phòng ban của dự án
                    dept = project.departments.first() if project.departments.exists() else dept_it
                    suitable_employees = [e for e in employees if e.department == dept and e != employee1]
                    if not suitable_employees:
                        suitable_employees = [e for e in employees if e != employee1]
                    assigned_emp = random.choice(suitable_employees) if suitable_employees else random.choice([e for e in employees if e != employee1])
                    
                    status = random.choice(task_statuses)
                    days_ago = random.randint(1, 60)
                    due_days = random.randint(1, 90)
                    
                    task, created = Task.objects.get_or_create(
                        project=project,
                        name=f'{task_name} - {project.name}',
                        defaults={
                            'description': f'{task_name} cho dự án {project.name}',
                            'status': status,
                            'department': dept,
                            'assigned_to': assigned_emp,
                            'assignment_status': 'in_progress' if status == 'in_progress' else ('completed' if status == 'done' else 'pending'),
                            'due_date': timezone.now().date() + timedelta(days=due_days),
                            'estimated_hours': Decimal(str(random.randint(20, 100))),
                            'started_at': timezone.now() - timedelta(days=days_ago) if status != 'todo' else None,
                            'created_by': manager_user,
                        }
                    )
                    if created:
                        task_count += 1

        created_counts['Task'] = task_count
        self.stdout.write(f'   [OK] Da tao {task_count} cong viec (employee1 duoc assign {employee1_task_count} tasks)')

        # 11.1 Thông báo giao việc mẫu cho employee1
        try:
            t = Task.objects.filter(assigned_to=employee1).select_related('project').first()
            if t and getattr(employee1, "user", None):
                NotificationService.notify(
                    user=employee1.user,
                    title=f"Bạn được giao công việc: {t.name}",
                    message=f"Bạn được giao công việc \"{t.name}\" trong dự án \"{t.project.name}\".",
                    level=Notification.LEVEL_INFO,
                    url=f"/projects/tasks/{t.pk}/edit/",
                    actor=manager_user,
                    dedupe_minutes=0,
                )
        except Exception:
            pass

        # 12. Tạo Ghi chép Thời gian (30 entries)
        self.stdout.write('\n[INFO] Dang tao Ghi chep Thoi gian...')
        tasks = Task.objects.all()
        time_entry_count = 0
        employee1_time_entry_count = 0
        
        # Đảm bảo employee1 có ít nhất 10-12 time entries từ các tasks được assign
        employee1_tasks = Task.objects.filter(assigned_to=employee1)
        for task in employee1_tasks[:12]:
            # Tạo 1-2 time entries cho mỗi task của employee1
            for i in range(random.randint(1, 2)):
                date_offset = random.randint(1, 20)
                hours = Decimal(str(random.uniform(6, 8)))
                
                time_entry, created = TimeEntry.objects.get_or_create(
                    task=task,
                    employee=employee1,
                    date=timezone.now().date() - timedelta(days=date_offset + i),
                    defaults={
                        'hours': hours,
                        'description': f'Lam viec tren task {task.name}',
                        'created_by': employee_user,
                    }
                )
                if created:
                    time_entry_count += 1
                    employee1_time_entry_count += 1
        
        # Tạo time entries cho các nhân viên khác
        remaining_count = 30 - time_entry_count
        for _ in range(remaining_count):
            task = random.choice(list(tasks))
            # Chọn nhân viên từ allocation hoặc assigned_to
            if task.assigned_to and task.assigned_to != employee1:
                emp = task.assigned_to
            else:
                emp = random.choice([e for e in employees if e != employee1])
            
            date_offset = random.randint(1, 30)
            hours = Decimal(str(random.uniform(4, 8)))
            
            time_entry, created = TimeEntry.objects.get_or_create(
                task=task,
                employee=emp,
                date=timezone.now().date() - timedelta(days=date_offset),
                defaults={
                    'hours': hours,
                    'description': f'Lam viec tren task {task.name}',
                    'created_by': manager_user,
                }
            )
            if created:
                time_entry_count += 1

        created_counts['TimeEntry'] = time_entry_count
        self.stdout.write(f'   [OK] Da tao {time_entry_count} ghi chep thoi gian (employee1 co {employee1_time_entry_count} entries)')

        # 13. Tạo Đánh giá Hiệu suất
        self.stdout.write('\n[INFO] Dang tao Danh gia Hieu suat...')
        score_count = 0
        
        # Đảm bảo employee1 có ít nhất 2-3 performance scores từ các dự án được phân bổ
        employee1_projects = [a.project for a in ResourceAllocation.objects.filter(employee=employee1)]
        employee1_score_count = 0
        for project in employee1_projects[:3]:
            period_start = timezone.now().date() - timedelta(days=random.randint(30, 90))
            
            score, created = PerformanceScore.objects.get_or_create(
                employee=employee1,
                project=project,
                period_start=period_start,
                defaults={
                    'overall_score': Decimal(str(random.uniform(80, 95))),
                    'efficiency_score': Decimal(str(random.uniform(82, 95))),
                    'quality_score': Decimal(str(random.uniform(85, 95))),
                    'productivity_score': Decimal(str(random.uniform(80, 92))),
                    'period_end': timezone.now().date(),
                    'notes': f'Nhan vien lam viec hieu qua, hoan thanh dung deadline, co trach nhiem cao',
                    'created_by': manager_user,
                }
            )
            if created:
                score_count += 1
                employee1_score_count += 1
        
        # Tạo performance scores cho các nhân viên khác
        other_employees = [e for e in employees[:5] if e != employee1]
        for emp in other_employees:
            project = random.choice(projects[:3])
            period_start = timezone.now().date() - timedelta(days=random.randint(30, 90))
            
            score, created = PerformanceScore.objects.get_or_create(
                employee=emp,
                project=project,
                period_start=period_start,
                defaults={
                    'overall_score': Decimal(str(random.uniform(70, 95))),
                    'efficiency_score': Decimal(str(random.uniform(75, 95))),
                    'quality_score': Decimal(str(random.uniform(75, 95))),
                    'productivity_score': Decimal(str(random.uniform(70, 90))),
                    'period_end': timezone.now().date(),
                    'notes': f'Nhan vien lam viec hieu qua, hoan thanh dung deadline',
                    'created_by': manager_user,
                }
            )
            if created:
                score_count += 1

        created_counts['PerformanceScore'] = score_count
        self.stdout.write(f'   [OK] Da tao {score_count} danh gia hieu suat (employee1 co {employee1_score_count} danh gia)')

        # 14. Tạo Personnel Recommendations
        self.stdout.write('\n[INFO] Dang tao Personnel Recommendations...')
        rec_count = 0
        for project in projects[:3]:  # Tạo recommendation cho 3 dự án đầu
            if project.budget_for_personnel > 0:
                # Tạo 1-2 recommendations cho mỗi dự án
                for opt_goal in ['balanced', 'performance', 'cost']:
                    # Chọn 3-4 nhân viên phù hợp
                    suitable_emps = [e for e in employees if e.department in project.departments.all()] or employees[:4]
                    selected_emps = random.sample(suitable_emps, min(4, len(suitable_emps)))
                    
                    total_cost = Decimal('0')
                    details_data = []
                    for emp in selected_emps:
                        allocation_pct = Decimal(str(random.randint(20, 60)))
                        estimated_hours = Decimal(str(random.randint(100, 200)))
                        estimated_cost = emp.hourly_rate * estimated_hours * (allocation_pct / 100)
                        total_cost += estimated_cost
                        
                        details_data.append({
                            'employee': emp,
                            'allocation_percentage': allocation_pct,
                            'estimated_hours': estimated_hours,
                            'estimated_cost': estimated_cost,
                            'reasoning': f'Nhan vien co kinh nghiem va phu hop voi du an',
                        })
                    
                    # Điều chỉnh nếu vượt budget
                    if total_cost > project.budget_for_personnel:
                        scale_factor = project.budget_for_personnel / total_cost
                        for detail in details_data:
                            detail['estimated_cost'] *= scale_factor
                            detail['estimated_hours'] *= scale_factor
                        total_cost = project.budget_for_personnel
                    
                    rec, created = PersonnelRecommendation.objects.get_or_create(
                        project=project,
                        optimization_goal=opt_goal,
                        reasoning=f'De xuat nhan su cho du an {project.name} theo muc tieu {opt_goal}',
                        defaults={
                            'total_estimated_cost': total_cost,
                            'created_by': manager_user,
                        }
                    )
                    if created:
                        for detail_data in details_data:
                            PersonnelRecommendationDetail.objects.create(
                                recommendation=rec,
                                employee=detail_data['employee'],
                                allocation_percentage=detail_data['allocation_percentage'],
                                estimated_hours=detail_data['estimated_hours'],
                                estimated_cost=detail_data['estimated_cost'],
                                reasoning=detail_data['reasoning'],
                                created_by=manager_user,
                            )
                        rec_count += 1

        created_counts['PersonnelRecommendation'] = rec_count
        self.stdout.write(f'   [OK] Da tao {rec_count} de xuat nhan su')

        # Tổng kết
        total_created = sum(created_counts.values())
        
        self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Da import thanh cong {total_created} ban ghi:'))
        for model_name, count in created_counts.items():
            if count > 0:
                self.stdout.write(f'   - {model_name}: {count} ban ghi')

        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Hoan tat! Data da duoc gan cho:'))
        self.stdout.write(f'   - Quan ly: {manager_user.email}')
        self.stdout.write(f'   - Nhan vien: {employee_user.email} (gan cho nhan vien {employee1.email})')
