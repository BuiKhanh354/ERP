"""
Django management command để xóa và tạo lại dữ liệu mẫu cho user cụ thể.

Chạy lệnh:
    python manage.py reset_sample_data --email thanhhung111120021@gmail.com

Script này sẽ:
1. Xóa toàn bộ dữ liệu mẫu hiện tại của user (nếu có)
2. Tạo dữ liệu mẫu mới và gán created_by cho user đó
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from resources.models import Department, Employee, ResourceAllocation
from clients.models import Client, Contact, ClientInteraction
from projects.models import Project, Task, TimeEntry
from budgeting.models import BudgetCategory, Budget, Expense
from performance.models import PerformanceScore, PerformanceMetric


class Command(BaseCommand):
    help = 'Xóa và tạo lại dữ liệu mẫu cho user cụ thể'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email của user để gán dữ liệu mẫu',
        )
        parser.add_argument(
            '--clear-all',
            action='store_true',
            help='Xóa tất cả dữ liệu mẫu (không chỉ của user)',
        )

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        clear_all = options.get('clear_all', False)
        
        # Tìm user
        try:
            user = User.objects.get(email=email)
            self.stdout.write(self.style.SUCCESS(f'[OK] Tim thay user: {user.username} ({user.email})'))
        except User.DoesNotExist:
            raise CommandError(f'[ERROR] Khong tim thay user voi email: {email}')

        # Xóa dữ liệu mẫu
        self.stdout.write(self.style.WARNING('\n[DANG XOA] Dang xoa du lieu mau cu...'))
        if clear_all:
            self.clear_all_sample_data()
        else:
            self.clear_user_sample_data(user)
        
        # Tạo dữ liệu mẫu mới
        self.stdout.write(self.style.SUCCESS('\n[DANG TAO] Dang tao du lieu mau moi...'))
        
        # Tạo theo thứ tự phụ thuộc
        departments = self.create_departments(user)
        employees = self.create_employees(user, departments)
        clients = self.create_clients(user)
        contacts = self.create_contacts(user, clients)
        projects = self.create_projects(user, clients)
        tasks = self.create_tasks(user, projects, employees)
        budget_categories = self.create_budget_categories(user)
        budgets = self.create_budgets(user, projects, budget_categories)
        expenses = self.create_expenses(user, projects, budgets, budget_categories)
        allocations = self.create_resource_allocations(user, employees, projects)
        performance_scores = self.create_performance_scores(user, employees, projects)
        time_entries = self.create_time_entries(user, tasks, employees)
        interactions = self.create_client_interactions(user, clients, contacts)

        self.stdout.write(self.style.SUCCESS('\n[HOAN TAT] Hoan tat tao du lieu mau!'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(departments)} phong ban'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(employees)} nhan su'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(clients)} khach hang'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(contacts)} lien he'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(projects)} du an'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(tasks)} cong viec'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(budgets)} ngan sach'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(expenses)} chi phi'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(allocations)} phan bo nhan su'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(performance_scores)} diem hieu suat'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(time_entries)} ghi chep thoi gian'))
        self.stdout.write(self.style.SUCCESS(f'  - {len(interactions)} tuong tac khach hang'))
        self.stdout.write(self.style.SUCCESS(f'\n[THANH CONG] Tat ca du lieu da duoc gan cho user: {user.username}'))

    def clear_all_sample_data(self):
        """Xóa tất cả dữ liệu mẫu."""
        TimeEntry.objects.all().delete()
        ClientInteraction.objects.all().delete()
        PerformanceScore.objects.all().delete()
        PerformanceMetric.objects.all().delete()
        Expense.objects.all().delete()
        Budget.objects.all().delete()
        ResourceAllocation.objects.all().delete()
        Task.objects.all().delete()
        Project.objects.all().delete()
        Contact.objects.all().delete()
        Client.objects.all().delete()
        Employee.objects.all().delete()
        # Không xóa Department và BudgetCategory vì có thể shared
        self.stdout.write(self.style.SUCCESS('  [OK] Da xoa tat ca du lieu mau'))

    def clear_user_sample_data(self, user):
        """Xóa dữ liệu mẫu của user cụ thể."""
        TimeEntry.objects.filter(task__project__created_by=user).delete()
        ClientInteraction.objects.filter(created_by=user).delete()
        PerformanceScore.objects.filter(created_by=user).delete()
        PerformanceMetric.objects.filter(created_by=user).delete()
        Expense.objects.filter(created_by=user).delete()
        Budget.objects.filter(project__created_by=user).delete()
        ResourceAllocation.objects.filter(project__created_by=user).delete()
        Task.objects.filter(project__created_by=user).delete()
        Project.objects.filter(created_by=user).delete()
        Contact.objects.filter(created_by=user).delete()
        Client.objects.filter(created_by=user).delete()
        Employee.objects.filter(created_by=user).delete()
        self.stdout.write(self.style.SUCCESS(f'  [OK] Da xoa du lieu mau cua user: {user.username}'))

    def create_departments(self, user):
        """Tao phong ban mau."""
        self.stdout.write('  Dang tao phong ban...')
        departments_data = [
            ('Phòng Kỹ thuật', 'Phòng phát triển và triển khai công nghệ'),
            ('Phòng Kinh doanh', 'Phòng phụ trách bán hàng và marketing'),
            ('Phòng Nhân sự', 'Phòng quản lý nhân sự và tuyển dụng'),
            ('Phòng Tài chính', 'Phòng quản lý tài chính và kế toán'),
            ('Phòng Vận hành', 'Phòng vận hành và hỗ trợ khách hàng'),
        ]

        departments = []
        for name, description in departments_data:
            dept, created = Department.objects.get_or_create(
                name=name,
                defaults={'description': description, 'created_by': user}
            )
            if not created:
                # Cập nhật created_by nếu đã tồn tại
                dept.created_by = user
                dept.save()
            departments.append(dept)

        return departments

    def create_employees(self, user, departments):
        """Tao nhan su mau."""
        self.stdout.write('  Dang tao nhan su...')
        employees_data = [
            ('EMP001', 'Nguyễn', 'Văn A', 'nguyen.van.a@example.com', '0901234567', 'Trưởng phòng Kỹ thuật', 'full_time', 500000),
            ('EMP002', 'Trần', 'Thị B', 'tran.thi.b@example.com', '0901234568', 'Kỹ sư Phần mềm', 'full_time', 400000),
            ('EMP003', 'Lê', 'Văn C', 'le.van.c@example.com', '0901234569', 'Kỹ sư Phần mềm', 'full_time', 400000),
            ('EMP004', 'Phạm', 'Thị D', 'pham.thi.d@example.com', '0901234570', 'Nhân viên Kinh doanh', 'full_time', 350000),
            ('EMP005', 'Hoàng', 'Văn E', 'hoang.van.e@example.com', '0901234571', 'Chuyên viên Tư vấn', 'full_time', 380000),
            ('EMP006', 'Vũ', 'Thị F', 'vu.thi.f@example.com', '0901234572', 'Trưởng phòng Nhân sự', 'full_time', 450000),
            ('EMP007', 'Đặng', 'Văn G', 'dang.van.g@example.com', '0901234573', 'Kế toán trưởng', 'full_time', 420000),
            ('EMP008', 'Bùi', 'Thị H', 'bui.thi.h@example.com', '0901234574', 'Nhân viên Kế toán', 'full_time', 300000),
            ('EMP009', 'Đỗ', 'Văn I', 'do.van.i@example.com', '0901234575', 'Chuyên viên Hỗ trợ', 'full_time', 320000),
            ('EMP010', 'Ngô', 'Thị K', 'ngo.thi.k@example.com', '0901234576', 'Thực tập sinh', 'intern', 100000),
        ]

        employees = []
        dept_index = 0
        for emp_id, first_name, last_name, email, phone, position, emp_type, hourly_rate in employees_data:
            department = departments[dept_index % len(departments)]
            dept_index += 1

            emp, created = Employee.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    'user': None,  # Không liên kết với User account
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                    'department': department,
                    'position': position,
                    'employment_type': emp_type,
                    'hourly_rate': Decimal(str(hourly_rate)),
                    'hire_date': timezone.now().date() - timedelta(days=random.randint(30, 1000)),
                    'is_active': True,
                    'created_by': user,
                }
            )
            if not created:
                emp.created_by = user
                emp.save()
            employees.append(emp)

        # Cập nhật manager cho các phòng ban
        if len(employees) >= 5:
            departments[0].manager = employees[0]
            departments[0].created_by = user
            departments[0].save()
            departments[2].manager = employees[5]
            departments[2].created_by = user
            departments[2].save()
            departments[3].manager = employees[6]
            departments[3].created_by = user
            departments[3].save()

        return employees

    def create_clients(self, user):
        """Tao khach hang mau."""
        self.stdout.write('  Dang tao khach hang...')
        clients_data = [
            ('Công ty ABC', 'company', 'active', 'abc@example.com', '0241234567', '123 Đường ABC, Hà Nội', 'https://abc.com', 'Công nghệ thông tin', 'Khách hàng lớn, hợp tác lâu dài'),
            ('Công ty XYZ', 'company', 'active', 'xyz@example.com', '0241234568', '456 Đường XYZ, TP.HCM', 'https://xyz.com', 'Tài chính', 'Khách hàng tiềm năng'),
            ('Công ty DEF', 'company', 'prospect', 'def@example.com', '0241234569', '789 Đường DEF, Đà Nẵng', '', 'Sản xuất', 'Đang thương thảo hợp đồng'),
            ('Nguyễn Văn M', 'individual', 'active', 'nguyen.van.m@example.com', '0901234577', '321 Đường MNO, Hà Nội', '', '', 'Khách hàng cá nhân'),
            ('Công ty GHI', 'company', 'inactive', 'ghi@example.com', '0241234570', '654 Đường GHI, Cần Thơ', '', 'Giáo dục', 'Khách hàng cũ, không còn hợp tác'),
        ]

        clients = []
        for name, client_type, status, email, phone, address, website, industry, notes in clients_data:
            client, created = Client.objects.get_or_create(
                name=name,
                defaults={
                    'client_type': client_type,
                    'status': status,
                    'email': email,
                    'phone': phone,
                    'address': address,
                    'website': website,
                    'industry': industry,
                    'notes': notes,
                    'created_by': user,
                }
            )
            if not created:
                client.created_by = user
                client.save()
            clients.append(client)

        return clients

    def create_contacts(self, user, clients):
        """Tao lien he mau."""
        self.stdout.write('  Dang tao lien he...')
        contacts_data = [
            (0, 'Nguyễn', 'Văn P', 'nguyen.van.p@example.com', '0901234578', 'Giám đốc', True),
            (0, 'Trần', 'Thị Q', 'tran.thi.q@example.com', '0901234579', 'Trưởng phòng', False),
            (1, 'Lê', 'Văn R', 'le.van.r@example.com', '0901234580', 'Giám đốc', True),
            (1, 'Phạm', 'Thị S', 'pham.thi.s@example.com', '0901234581', 'Phó giám đốc', False),
            (2, 'Hoàng', 'Văn T', 'hoang.van.t@example.com', '0901234582', 'Giám đốc', True),
            (3, 'Vũ', 'Thị U', 'vu.thi.u@example.com', '0901234583', 'Chủ sở hữu', True),
        ]

        contacts = []
        for client_idx, first_name, last_name, email, phone, position, is_primary in contacts_data:
            if client_idx < len(clients):
                contact, created = Contact.objects.get_or_create(
                    client=clients[client_idx],
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'phone': phone,
                        'position': position,
                        'is_primary': is_primary,
                        'created_by': user,
                    }
                )
                if not created:
                    contact.created_by = user
                    contact.save()
                contacts.append(contact)

        return contacts

    def create_projects(self, user, clients):
        """Tao du an mau."""
        self.stdout.write('  Dang tao du an...')
        today = timezone.now().date()
        projects_data = [
            ('Dự án Hệ thống ERP', 'Phát triển hệ thống ERP cho công ty ABC', 'active', 'high', 30, 500000000, 250000000),
            ('Dự án Website Thương mại', 'Xây dựng website thương mại điện tử cho công ty XYZ', 'active', 'medium', 15, 200000000, 120000000),
            ('Dự án Ứng dụng Mobile', 'Phát triển ứng dụng mobile cho công ty DEF', 'planning', 'high', 20, 300000000, 0),
            ('Dự án Tư vấn CNTT', 'Tư vấn chuyển đổi số cho khách hàng cá nhân', 'active', 'low', 5, 50000000, 30000000),
            ('Dự án Bảo trì Hệ thống', 'Bảo trì và nâng cấp hệ thống cũ', 'on_hold', 'medium', 10, 100000000, 50000000),
            ('Dự án Hoàn thành', 'Dự án đã hoàn thành thành công', 'completed', 'medium', 8, 150000000, 150000000),
        ]

        projects = []
        for name, description, status, priority, estimated_employees, estimated_budget, actual_budget in projects_data:
            client = random.choice(clients)
            
            start_date = today - timedelta(days=random.randint(30, 180))
            if status == 'completed':
                end_date = today - timedelta(days=random.randint(1, 30))
            elif status == 'active':
                end_date = today + timedelta(days=random.randint(30, 180))
            else:
                end_date = None

            project, created = Project.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'client': client,
                    'status': status,
                    'priority': priority,
                    'start_date': start_date,
                    'end_date': end_date,
                    'estimated_budget': Decimal(str(estimated_budget)),
                    'actual_budget': Decimal(str(actual_budget)),
                    'estimated_employees': estimated_employees,
                    'created_by': user,
                }
            )
            if not created:
                project.created_by = user
                project.save()
            projects.append(project)

        return projects

    def create_tasks(self, user, projects, employees):
        """Tao cong viec mau."""
        self.stdout.write('  Dang tao cong viec...')
        tasks_data = [
            ('Phân tích yêu cầu', 'Phân tích và thu thập yêu cầu từ khách hàng', 'done', 40, 35),
            ('Thiết kế hệ thống', 'Thiết kế kiến trúc và database', 'done', 60, 55),
            ('Phát triển Backend', 'Phát triển API và logic nghiệp vụ', 'in_progress', 120, 80),
            ('Phát triển Frontend', 'Phát triển giao diện người dùng', 'in_progress', 100, 60),
            ('Kiểm thử', 'Kiểm thử chức năng và sửa lỗi', 'review', 40, 20),
            ('Triển khai', 'Triển khai hệ thống lên production', 'todo', 20, 0),
            ('Bảo trì', 'Bảo trì và hỗ trợ sau triển khai', 'todo', 10, 0),
        ]

        tasks = []
        for project in projects:
            num_tasks = random.randint(3, 5)
            selected_tasks = random.sample(tasks_data, min(num_tasks, len(tasks_data)))
            
            for task_name, task_desc, status, estimated_hours, actual_hours in selected_tasks:
                assigned_employee = random.choice(employees) if employees else None
                due_date = timezone.now().date() + timedelta(days=random.randint(-30, 60))

                task, created = Task.objects.get_or_create(
                    project=project,
                    name=f"{project.name} - {task_name}",
                    defaults={
                        'description': task_desc,
                        'status': status,
                        'assigned_to': assigned_employee,
                        'due_date': due_date,
                        'estimated_hours': Decimal(str(estimated_hours)),
                        'actual_hours': Decimal(str(actual_hours)),
                        'created_by': user,
                    }
                )
                if not created:
                    task.created_by = user
                    task.save()
                tasks.append(task)

        return tasks

    def create_budget_categories(self, user):
        """Tao danh muc ngan sach."""
        self.stdout.write('  Dang tao danh muc ngan sach...')
        categories_data = [
            ('Nhân sự', 'Chi phí nhân sự và lương'),
            ('Vật tư', 'Chi phí vật tư và nguyên liệu'),
            ('Thiết bị', 'Chi phí mua sắm thiết bị'),
            ('Dịch vụ', 'Chi phí dịch vụ bên ngoài'),
            ('Du lịch', 'Chi phí đi lại và công tác'),
            ('Khác', 'Các chi phí khác'),
        ]

        categories = []
        for name, description in categories_data:
            cat, created = BudgetCategory.objects.get_or_create(
                name=name,
                defaults={'description': description, 'created_by': user}
            )
            if not created:
                cat.created_by = user
                cat.save()
            categories.append(cat)

        return categories

    def create_budgets(self, user, projects, categories):
        """Tao ngan sach mau."""
        self.stdout.write('  Dang tao ngan sach...')
        budgets = []
        current_year = timezone.now().year

        for project in projects:
            num_budgets = random.randint(2, 4)
            selected_categories = random.sample(categories, min(num_budgets, len(categories)))

            for category in selected_categories:
                allocated = Decimal(str(random.randint(10000000, 100000000)))
                spent = allocated * Decimal(str(random.uniform(0.3, 0.9)))

                budget, created = Budget.objects.get_or_create(
                    project=project,
                    category=category,
                    fiscal_year=current_year,
                    defaults={
                        'allocated_amount': allocated,
                        'spent_amount': spent,
                        'notes': f'Ngân sách {category.name} cho {project.name}',
                        'created_by': user,
                    }
                )
                if not created:
                    budget.created_by = user
                    budget.save()
                budgets.append(budget)

        return budgets

    def create_expenses(self, user, projects, budgets, categories):
        """Tao chi phi mau."""
        self.stdout.write('  Dang tao chi phi...')
        expenses = []
        expense_types = ['labor', 'material', 'equipment', 'travel', 'other']
        vendors = ['Nhà cung cấp A', 'Nhà cung cấp B', 'Nhà cung cấp C', 'Nội bộ', '']

        for project in projects:
            num_expenses = random.randint(5, 10)
            project_budgets = [b for b in budgets if b.project == project]

            for _ in range(num_expenses):
                category = random.choice(categories)
                budget = random.choice(project_budgets) if project_budgets else None
                expense_type = random.choice(expense_types)
                amount = Decimal(str(random.randint(100000, 5000000)))
                expense_date = timezone.now().date() - timedelta(days=random.randint(1, 90))

                expense = Expense.objects.create(
                    project=project,
                    budget=budget,
                    category=category,
                    expense_type=expense_type,
                    amount=amount,
                    description=f'Chi phí {expense_type} cho {project.name}',
                    expense_date=expense_date,
                    vendor=random.choice(vendors),
                    invoice_number=f'INV-{random.randint(1000, 9999)}' if random.choice([True, False]) else '',
                    created_by=user,
                )
                expenses.append(expense)

        return expenses

    def create_resource_allocations(self, user, employees, projects):
        """Tao phan bo nhan su."""
        self.stdout.write('  Dang tao phan bo nhan su...')
        allocations = []

        for project in projects:
            num_employees = random.randint(2, min(5, len(employees)))
            selected_employees = random.sample(employees, num_employees)

            for employee in selected_employees:
                allocation_pct = Decimal(str(random.randint(20, 100)))
                start_date = project.start_date or timezone.now().date()
                end_date = project.end_date

                allocation, created = ResourceAllocation.objects.get_or_create(
                    employee=employee,
                    project=project,
                    start_date=start_date,
                    defaults={
                        'allocation_percentage': allocation_pct,
                        'end_date': end_date,
                        'notes': f'Phân bổ {allocation_pct}% cho {project.name}',
                        'created_by': user,
                    }
                )
                if not created:
                    allocation.created_by = user
                    allocation.save()
                if created:
                    allocations.append(allocation)

        return allocations

    def create_performance_scores(self, user, employees, projects):
        """Tao diem hieu suat."""
        self.stdout.write('  Dang tao diem hieu suat...')
        scores = []
        today = timezone.now().date()
        period_start = today - timedelta(days=30)
        period_end = today

        for employee in employees[:8]:
            overall = Decimal(str(random.uniform(70, 95)))
            efficiency = Decimal(str(random.uniform(70, 95)))
            quality = Decimal(str(random.uniform(75, 95)))
            productivity = Decimal(str(random.uniform(70, 95)))

            project = random.choice(projects) if random.choice([True, False]) else None

            score = PerformanceScore.objects.create(
                employee=employee,
                project=project,
                overall_score=overall,
                efficiency_score=efficiency,
                quality_score=quality,
                productivity_score=productivity,
                period_start=period_start,
                period_end=period_end,
                notes=f'Đánh giá hiệu suất tháng {period_start.month}/{period_start.year}',
                created_by=user,
            )
            scores.append(score)

        return scores

    def create_time_entries(self, user, tasks, employees):
        """Tao ghi chep thoi gian."""
        self.stdout.write('  Dang tao ghi chep thoi gian...')
        entries = []
        today = timezone.now().date()

        for task in tasks[:20]:
            if task.assigned_to:
                num_entries = random.randint(3, 5)
                for _ in range(num_entries):
                    entry_date = today - timedelta(days=random.randint(1, 30))
                    hours = Decimal(str(random.uniform(2, 8)))

                    entry, created = TimeEntry.objects.get_or_create(
                        task=task,
                        employee=task.assigned_to,
                        date=entry_date,
                        defaults={
                            'hours': hours,
                            'description': f'Làm việc trên {task.name}',
                            'created_by': user,
                        }
                    )
                    if created:
                        entries.append(entry)

        return entries

    def create_client_interactions(self, user, clients, contacts):
        """Tao tuong tac khach hang."""
        self.stdout.write('  Dang tao tuong tac khach hang...')
        interactions = []
        interaction_types = ['meeting', 'call', 'email', 'proposal', 'contract', 'other']
        subjects = [
            'Họp bàn về dự án',
            'Gọi điện trao đổi',
            'Gửi email đề xuất',
            'Trình bày đề xuất',
            'Ký hợp đồng',
            'Theo dõi tiến độ',
        ]

        for client in clients:
            num_interactions = random.randint(2, 4)
            client_contacts = [c for c in contacts if c.client == client]

            for _ in range(num_interactions):
                interaction_type = random.choice(interaction_types)
                subject = random.choice(subjects)
                contact = random.choice(client_contacts) if client_contacts else None
                date = timezone.now() - timedelta(days=random.randint(1, 90))
                follow_up = random.choice([True, False])
                follow_up_date = date + timedelta(days=random.randint(1, 30)) if follow_up else None

                interaction = ClientInteraction.objects.create(
                    client=client,
                    contact=contact,
                    interaction_type=interaction_type,
                    date=date,
                    subject=subject,
                    description=f'{interaction_type.title()}: {subject} với {client.name}',
                    follow_up_required=follow_up,
                    follow_up_date=follow_up_date,
                    created_by=user,
                )
                interactions.append(interaction)

        return interactions
