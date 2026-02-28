"""AI service using Gemini model."""
import json
import warnings
# Suppress deprecation warning for google.generativeai
# TODO: Migrate to google.genai when stable
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    import google.generativeai as genai

from django.conf import settings
from django.db.models import Sum, Avg
from .models import AIInsight
from resources.models import Employee
from projects.models import Project, Task, TimeEntry
from performance.models import PerformanceScore
from budgeting.models import Budget, Expense
from clients.models import Client
from decimal import Decimal


class AIService:
    """Service class for AI-related operations using Gemini."""

    @staticmethod
    def _check_user_has_data(user, data_type='general'):
        """
        Kiểm tra xem user có đủ data để phân tích AI không.
        
        Args:
            user: User object
            data_type: Loại data cần kiểm tra ('general', 'sales', 'purchasing', 'expense', 'project', 'employee')
        
        Returns:
            tuple: (has_data: bool, message: str)
        """
        is_manager = hasattr(user, 'profile') and user.profile.is_manager()
        
        if data_type == 'general':
            # Kiểm tra data tổng quát cho dashboard
            if is_manager:
                has_projects = Project.objects.exists()
                has_tasks = Task.objects.exists()
                has_budgets = Budget.objects.exists()
                has_expenses = Expense.objects.exists()
            else:
                # Nhân viên kiểm tra từ ResourceAllocation và tasks được assign
                from resources.models import ResourceAllocation
                employee = getattr(user, 'employee', None)
                if employee:
                    allocated_project_ids = ResourceAllocation.objects.filter(
                        employee=employee
                    ).values_list('project_id', flat=True).distinct()
                    has_projects = Project.objects.filter(id__in=allocated_project_ids).exists()
                    has_tasks = Task.objects.filter(assigned_to=employee).exists()
                    has_budgets = Budget.objects.filter(project_id__in=allocated_project_ids).exists()
                    has_expenses = Expense.objects.filter(project_id__in=allocated_project_ids).exists()
                else:
                    # Nếu không có employee record, không có data
                    has_projects = False
                    has_tasks = False
                    has_budgets = False
                    has_expenses = False
            
            if not (has_projects or has_tasks or has_budgets or has_expenses):
                return False, "Chưa có đủ dữ liệu để phân tích. Vui lòng tạo dự án, công việc, ngân sách hoặc chi phí trước."
            return True, ""
        
        elif data_type == 'sales':
            # Kiểm tra data cho sales analysis
            if is_manager:
                has_clients = Client.objects.exists()
                has_projects = Project.objects.exists()
            else:
                # Nhân viên kiểm tra từ ResourceAllocation
                from resources.models import ResourceAllocation
                employee = getattr(user, 'employee', None)
                if employee:
                    allocated_project_ids = ResourceAllocation.objects.filter(
                        employee=employee
                    ).values_list('project_id', flat=True).distinct()
                    has_projects = Project.objects.filter(id__in=allocated_project_ids).exists()
                    # Clients từ projects được phân bổ
                    has_clients = Client.objects.filter(
                        projects__id__in=allocated_project_ids
                    ).exists()
                else:
                    has_clients = False
                    has_projects = False
            
            if not (has_clients or has_projects):
                return False, "Chưa có đủ dữ liệu để phân tích hiệu suất bán hàng. Vui lòng tạo khách hàng hoặc dự án trước."
            return True, ""
        
        elif data_type == 'purchasing':
            # Kiểm tra data cho purchasing analysis
            if is_manager:
                has_expenses = Expense.objects.exists()
                has_budgets = Budget.objects.exists()
            else:
                # Nhân viên kiểm tra từ ResourceAllocation
                from resources.models import ResourceAllocation
                employee = getattr(user, 'employee', None)
                if employee:
                    allocated_project_ids = ResourceAllocation.objects.filter(
                        employee=employee
                    ).values_list('project_id', flat=True).distinct()
                    has_expenses = Expense.objects.filter(project_id__in=allocated_project_ids).exists()
                    has_budgets = Budget.objects.filter(project_id__in=allocated_project_ids).exists()
                else:
                    has_expenses = False
                    has_budgets = False
            
            if not (has_expenses or has_budgets):
                return False, "Chưa có đủ dữ liệu để phân tích mua hàng. Vui lòng tạo ngân sách hoặc chi phí trước."
            return True, ""
        
        elif data_type == 'expense':
            # Kiểm tra data cho expense optimization
            if is_manager:
                has_expenses = Expense.objects.exists()
            else:
                # Nhân viên kiểm tra từ ResourceAllocation
                from resources.models import ResourceAllocation
                employee = getattr(user, 'employee', None)
                if employee:
                    allocated_project_ids = ResourceAllocation.objects.filter(
                        employee=employee
                    ).values_list('project_id', flat=True).distinct()
                    has_expenses = Expense.objects.filter(project_id__in=allocated_project_ids).exists()
                else:
                    has_expenses = False
            
            if not has_expenses:
                return False, "Chưa có đủ dữ liệu để tối ưu chi tiêu. Vui lòng tạo chi phí trước."
            return True, ""
        
        elif data_type == 'project':
            # Kiểm tra data cho project analysis
            if is_manager:
                has_projects = Project.objects.exists()
                has_tasks = Task.objects.exists()
            else:
                # Nhân viên kiểm tra từ ResourceAllocation và tasks được assign
                from resources.models import ResourceAllocation
                employee = getattr(user, 'employee', None)
                if employee:
                    allocated_project_ids = ResourceAllocation.objects.filter(
                        employee=employee
                    ).values_list('project_id', flat=True).distinct()
                    has_projects = Project.objects.filter(id__in=allocated_project_ids).exists()
                    has_tasks = Task.objects.filter(assigned_to=employee).exists()
                else:
                    has_projects = False
                    has_tasks = False
            
            if not (has_projects or has_tasks):
                return False, "Chưa có đủ dữ liệu để phân tích dự án. Vui lòng tạo dự án hoặc công việc trước."
            return True, ""
        
        elif data_type == 'employee':
            # Kiểm tra data cho employee analysis
            if is_manager:
                has_employees = Employee.objects.exists()
                has_time_entries = TimeEntry.objects.exists()
            else:
                # Nhân viên chỉ xem chính mình
                employee = getattr(user, 'employee', None)
                if employee:
                    has_employees = True  # Có chính mình
                    has_time_entries = TimeEntry.objects.filter(employee=employee).exists()
                else:
                    has_employees = False
                    has_time_entries = False
            
            if not (has_employees or has_time_entries):
                return False, "Chưa có đủ dữ liệu để phân tích nhân sự. Vui lòng tạo nhân sự hoặc ghi chép thời gian trước."
            return True, ""
        
        return True, ""

    @staticmethod
    def _get_gemini_client():
        """Initialize and return Gemini client."""
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured in settings")
        genai.configure(api_key=api_key)
        # Use gemini-2.5-flash-lite - lightweight model optimized for speed and cost
        # According to docs: https://ai.google.dev/gemini-api/docs/models?hl=vi
        # gemini-2.5-flash-lite is optimized for faster responses and lower costs
        return genai.GenerativeModel('gemini-2.5-flash-lite')

    @staticmethod
    def _generate_insight(prompt, context_data=None):
        """Generate AI insight using Gemini."""
        try:
            model = AIService._get_gemini_client()
            
            full_prompt = prompt
            if context_data:
                full_prompt += f"\n\nContext Data:\n{json.dumps(context_data, indent=2)}"
            
            # Kiểm tra xem prompt có yêu cầu ngắn gọn không
            if "NGẮN GỌN" in prompt or "ngắn gọn" in prompt or "3-4 đoạn" in prompt or "RẤT NGẮN GỌN" in prompt or "CỰC KỲ NGẮN GỌN" in prompt or "QUY TẮC NGHIÊM NGẶT" in prompt:
                full_prompt += "\n\nCRITICAL FORMATTING RULES:\n"
                full_prompt += "- 'summary': Plain text ONLY, NO markdown, NO asterisks (*), NO JSON format, NO bold/italic, NO trailing commas\n"
                
                # Kiểm tra độ dài summary
                if "3 ĐOẠN" in prompt or "3 đoạn" in prompt or ("150 từ" in prompt and "tối đa 150 từ" in prompt):
                    full_prompt += "- Summary must be 3 PARAGRAPHS, each paragraph 2-3 sentences, MAX 150 words total (50 words per paragraph), separated by \\n\\n, NO trailing commas\n"
                    full_prompt += "- Paragraph 1: Deep analysis of project progress and results based on data\n"
                    full_prompt += "- Paragraph 2: Development solutions and improvement plans\n"
                    full_prompt += "- Paragraph 3: Future predictions and warnings\n"
                elif "50 từ" in prompt or "tối đa 50 từ" in prompt:
                    full_prompt += "- Summary must be 2 sentences, MAX 50 words total, each sentence max 25 words, NO trailing commas\n"
                elif "60 từ" in prompt or "tối đa 60 từ" in prompt:
                    full_prompt += "- Summary must be 2-3 sentences, MAX 60 words total, each sentence max 20 words, NO trailing commas\n"
                elif "CỰC KỲ NGẮN GỌN" in prompt or "80 từ" in prompt or "tối đa 80 từ" in prompt:
                    full_prompt += "- Summary must be 2-3 sentences, MAX 80 words total, each sentence max 25 words, NO trailing commas\n"
                else:
                    full_prompt += "- Summary must be 3-4 sentences, MAX 150 words total, NO trailing commas\n"
                
                # Kiểm tra xem có yêu cầu format với dấu gạch không
                use_dash_format = "- [" in prompt or "dấu gạch" in prompt.lower() or "Format: \"- [" in prompt
                
                if use_dash_format:
                    full_prompt += "- 'insights': Array of 3 items, each item MUST start with '- ' (dash and space), max 12 words, NO quotes, NO trailing commas\n"
                    full_prompt += "- 'recommendations': Array of 3 items, each item MUST start with '- ' (dash and space), max 18 words, NO quotes, NO trailing commas\n"
                else:
                    full_prompt += "- 'insights': Array of 3-4 items, each item max 15 words, plain text, no bullets, NO quotes, NO trailing commas\n"
                    full_prompt += "- 'recommendations': Array of 3-4 items, each item max 20 words, plain text, actionable, NO quotes, NO trailing commas\n"
                
                full_prompt += "- Remove ALL formatting: no *, **, quotes, trailing commas, or unnecessary punctuation\n"
                full_prompt += "- Return ONLY valid JSON, all text fields must be plain text without formatting\n"
                full_prompt += "- Be EXTREMELY CONCISE: avoid repetition, remove redundant words, focus on key points only"
            else:
                full_prompt += "\n\nPlease provide a structured JSON response with 'summary', 'insights' (array), and 'recommendations' (array)."
            
            response = model.generate_content(full_prompt)
            
            try:
                # Làm sạch response text trước khi parse JSON
                cleaned_text = response.text.strip()
                
                # Loại bỏ markdown code blocks nếu có
                if cleaned_text.startswith('```'):
                    cleaned_text = cleaned_text.split('```')[1]
                    if cleaned_text.startswith('json'):
                        cleaned_text = cleaned_text[4:]
                    cleaned_text = cleaned_text.strip()
                
                # Parse JSON
                result = json.loads(cleaned_text)
                
                # Làm sạch summary: loại bỏ dấu phẩy dư thừa ở cuối
                if 'summary' in result and isinstance(result['summary'], str):
                    result['summary'] = result['summary'].rstrip(',').strip()
                
                # Làm sạch insights và recommendations: đảm bảo format với dấu gạch
                if 'insights' in result and isinstance(result['insights'], list):
                    cleaned_insights = []
                    for item in result['insights']:
                        if isinstance(item, str):
                            # Loại bỏ dấu ngoặc kép và dấu phẩy dư thừa
                            item = item.strip().strip('"').strip("'").rstrip(',').strip()
                            # Đảm bảo có dấu gạch đầu dòng nếu prompt yêu cầu
                            if "- [" in prompt or "dấu gạch" in prompt.lower():
                                if not item.startswith('- '):
                                    item = '- ' + item.lstrip('-').strip()
                            cleaned_insights.append(item)
                    result['insights'] = cleaned_insights
                
                if 'recommendations' in result and isinstance(result['recommendations'], list):
                    cleaned_recommendations = []
                    for item in result['recommendations']:
                        if isinstance(item, str):
                            # Loại bỏ dấu ngoặc kép và dấu phẩy dư thừa
                            item = item.strip().strip('"').strip("'").rstrip(',').strip()
                            # Đảm bảo có dấu gạch đầu dòng nếu prompt yêu cầu
                            if "- [" in prompt or "dấu gạch" in prompt.lower():
                                if not item.startswith('- '):
                                    item = '- ' + item.lstrip('-').strip()
                            cleaned_recommendations.append(item)
                    result['recommendations'] = cleaned_recommendations
                
            except json.JSONDecodeError:
                # Nếu không parse được JSON, thử làm sạch và parse lại
                cleaned_text = response.text.strip()
                # Loại bỏ markdown nếu có
                if '```json' in cleaned_text:
                    cleaned_text = cleaned_text.split('```json')[1].split('```')[0].strip()
                elif '```' in cleaned_text:
                    cleaned_text = cleaned_text.split('```')[1].split('```')[0].strip()
                
                try:
                    result = json.loads(cleaned_text)
                    # Áp dụng làm sạch tương tự
                    if 'summary' in result:
                        result['summary'] = result['summary'].rstrip(',').strip()
                except:
                    result = {
                        "summary": response.text.rstrip(',').strip(),
                        "insights": [],
                        "recommendations": []
                    }
            
            return result
        except Exception as e:
            return {
                "summary": f"Error generating insight: {str(e)}",
                "insights": [],
                "recommendations": []
            }

    @staticmethod
    def analyze_resource_performance(employee_id):
        """Analyze resource performance and generate insights."""
        employee = Employee.objects.get(id=employee_id)
        
        time_entries = TimeEntry.objects.filter(employee=employee)
        total_hours = time_entries.aggregate(total=Sum('hours'))['total'] or 0
        
        scores = PerformanceScore.objects.filter(employee=employee)
        avg_score = scores.aggregate(avg=Avg('overall_score'))['avg'] or 0
        
        context = {
            "employee": {
                "name": employee.full_name,
                "position": employee.position,
                "department": employee.department.name if employee.department else None,
                "total_hours": float(total_hours),
                "average_score": float(avg_score) if avg_score else 0,
            }
        }
        
        prompt = (
            f"Phân tích hiệu suất làm việc của nhân sự {employee.full_name} trong doanh nghiệp dịch vụ.\n"
            f"- Sử dụng dữ liệu trong JSON context (tổng giờ làm, điểm hiệu suất trung bình, phòng ban).\n"
            f"- Đưa ra nhận định ngắn gọn về điểm mạnh, điểm yếu, rủi ro và tiềm năng phát triển.\n"
            f"- Đề xuất các hành động cụ thể để cải thiện hiệu suất và gắn kết với mục tiêu dự án.\n"
            f"- TRẢ LỜI HOÀN TOÀN BẰNG TIẾNG VIỆT.\n"
        )
        
        result = AIService._generate_insight(prompt, context)
        
        insight = AIInsight.objects.create(
            insight_type='resource_performance',
            title=f"Performance Analysis: {employee.full_name}",
            summary=result.get('summary', ''),
            insights=json.dumps(result.get('insights', [])),
            recommendations=json.dumps(result.get('recommendations', [])),
            context_data=json.dumps(context)
        )
        
        return {
            "insight_id": insight.id,
            "summary": result.get('summary', ''),
            "insights": result.get('insights', []),
            "recommendations": result.get('recommendations', [])
        }

    @staticmethod
    def recommend_project_staffing(project_id):
        """Recommend optimal project staffing."""
        project = Project.objects.get(id=project_id)
        
        tasks = project.tasks.all()
        allocations = project.allocations.all()
        
        # Kiểm tra data trước khi phân tích
        if not tasks.exists() and not allocations.exists():
            return {
                "summary": "Dự án chưa có công việc hoặc phân bổ nhân sự. Vui lòng thêm công việc hoặc phân bổ nhân sự trước khi phân tích.",
                "insights": [],
                "recommendations": [],
                "no_data": True
            }
        
        context = {
            "project": {
                "name": project.name,
                "status": project.status,
                "estimated_budget": float(project.estimated_budget),
                "total_tasks": tasks.count(),
                "allocations": [
                    {
                        "employee": alloc.employee.full_name,
                        "percentage": float(alloc.allocation_percentage)
                    }
                    for alloc in allocations
                ]
            }
        }
        
        prompt = (
            f"Phân tích dự án {project.name} và đề xuất phân bổ nhân sự tối ưu.\n"
            f"- Sử dụng dữ liệu trong JSON context (tổng số task, phân bổ nhân sự hiện tại, ngân sách).\n"
            f"- Xác định nơi đang thiếu/ thừa nhân sự, rủi ro quá tải hoặc thiếu nguồn lực.\n"
            f"- Đưa ra khuyến nghị cụ thể về điều chỉnh tỉ lệ phân bổ cho các nhân sự/nhóm.\n"
            f"- TRẢ LỜI HOÀN TOÀN BẰNG TIẾNG VIỆT.\n"
        )
        
        result = AIService._generate_insight(prompt, context)
        
        insight = AIInsight.objects.create(
            insight_type='project_staffing',
            title=f"Staffing Recommendation: {project.name}",
            summary=result.get('summary', ''),
            insights=json.dumps(result.get('insights', [])),
            recommendations=json.dumps(result.get('recommendations', [])),
            context_data=json.dumps(context)
        )
        
        return {
            "insight_id": insight.id,
            "summary": result.get('summary', ''),
            "insights": result.get('insights', []),
            "recommendations": result.get('recommendations', [])
        }

    @staticmethod
    def analyze_budget_patterns(project_id):
        """Analyze budget patterns and suggest optimizations."""
        project = Project.objects.get(id=project_id)
        
        budgets = Budget.objects.filter(project=project)
        expenses = Expense.objects.filter(project=project)
        
        total_allocated = budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
        total_spent = budgets.aggregate(total=Sum('spent_amount'))['total'] or 0
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
        
        context = {
            "project": {
                "name": project.name,
                "estimated_budget": float(project.estimated_budget),
                "total_allocated": float(total_allocated),
                "total_spent": float(total_spent),
                "total_expenses": float(total_expenses),
                "utilization": float((total_spent / total_allocated * 100) if total_allocated > 0 else 0)
            }
        }
        
        prompt = (
            f"Phân tích mô hình sử dụng ngân sách cho dự án {project.name}.\n"
            f"- Dựa trên dữ liệu trong JSON context: ngân sách dự kiến, đã phân bổ, đã chi, chi phí thực tế.\n"
            f"- Xác định hạng mục chi vượt/thiếu so với kế hoạch, đánh giá mức độ sử dụng ngân sách.\n"
            f"- Đề xuất các giải pháp tối ưu chi tiêu và phân bổ lại ngân sách nếu cần.\n"
            f"- TRẢ LỜI HOÀN TOÀN BẰNG TIẾNG VIỆT.\n"
        )
        
        result = AIService._generate_insight(prompt, context)
        
        insight = AIInsight.objects.create(
            insight_type='budget_optimization',
            title=f"Budget Analysis: {project.name}",
            summary=result.get('summary', ''),
            insights=json.dumps(result.get('insights', [])),
            recommendations=json.dumps(result.get('recommendations', [])),
            context_data=json.dumps(context)
        )
        
        return {
            "insight_id": insight.id,
            "summary": result.get('summary', ''),
            "insights": result.get('insights', []),
            "recommendations": result.get('recommendations', [])
        }

    @staticmethod
    def analyze_sales_performance(user=None):
        """Analyze sales data and provide improvement recommendations."""
        from clients.models import Client, ClientInteraction
        
        # Kiểm tra data trước khi phân tích
        if user:
            has_data, message = AIService._check_user_has_data(user, 'sales')
            if not has_data:
                return {
                    "summary": message,
                    "insights": [],
                    "recommendations": [],
                    "no_data": True
                }
            is_manager = hasattr(user, 'profile') and user.profile.is_manager()
            if is_manager:
                total_clients = Client.objects.count()
                active_clients = Client.objects.filter(status='active').count()
                total_projects = Project.objects.count()
                completed_projects = Project.objects.filter(status='completed').count()
            else:
                total_clients = Client.objects.filter(created_by=user).count()
                active_clients = Client.objects.filter(status='active', created_by=user).count()
                total_projects = Project.objects.filter(created_by=user).count()
                completed_projects = Project.objects.filter(status='completed', created_by=user).count()
        else:
            # Fallback cho backward compatibility
            total_clients = Client.objects.count()
            active_clients = Client.objects.filter(status='active').count()
            total_projects = Project.objects.count()
            completed_projects = Project.objects.filter(status='completed').count()
            
            if total_clients == 0 and total_projects == 0:
                return {
                    "summary": "Chưa có đủ dữ liệu để phân tích hiệu suất bán hàng. Vui lòng tạo khách hàng hoặc dự án trước.",
                    "insights": [],
                    "recommendations": [],
                    "no_data": True
                }
        total_revenue = Project.objects.aggregate(
            total=Sum('estimated_budget')
        )['total'] or 0
        
        if user and not (hasattr(user, 'profile') and user.profile.is_manager()):
            interactions = ClientInteraction.objects.filter(client__created_by=user)
        else:
            interactions = ClientInteraction.objects.all()
        recent_interactions = interactions.order_by('-date')[:20]
        
        context = {
            "sales_metrics": {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "conversion_rate": (active_clients / total_clients * 100) if total_clients > 0 else 0,
                "total_projects": total_projects,
                "completed_projects": completed_projects,
                "completion_rate": (completed_projects / total_projects * 100) if total_projects > 0 else 0,
                "total_revenue": float(total_revenue),
            },
            "recent_interactions": [
                {
                    "client": inter.client.name,
                    "type": inter.interaction_type,
                    "date": inter.date.isoformat(),
                    "follow_up_required": inter.follow_up_required
                }
                for inter in recent_interactions
            ]
        }
        
        prompt = (
            "Phân tích hiệu suất bán hàng dựa trên JSON context (khách hàng, tỉ lệ chuyển đổi, dự án, doanh thu, tương tác gần đây).\n"
            "YÊU CẦU:\n"
            "1) Tóm tắt NGẮN GỌN trong 2 đoạn, mỗi đoạn 2-3 câu, chỉ nêu ý chính, không rườm rà.\n"
            "2) Nêu rõ điểm nghẽn và cơ hội trong pipeline bán hàng.\n"
            "3) Đưa ra danh sách ngắn (3-4 mục) nhận định và đề xuất cải thiện, dễ hành động.\n"
            "4) TRẢ LỜI HOÀN TOÀN BẰNG TIẾNG VIỆT, văn phong súc tích.\n"
        )
        
        result = AIService._generate_insight(prompt, context)
        
        insight = AIInsight.objects.create(
            insight_type='sales_improvement',
            title="Sales Performance Analysis",
            summary=result.get('summary', ''),
            insights=json.dumps(result.get('insights', [])),
            recommendations=json.dumps(result.get('recommendations', [])),
            context_data=json.dumps(context)
        )
        
        return {
            "insight_id": insight.id,
            "summary": result.get('summary', ''),
            "insights": result.get('insights', []),
            "recommendations": result.get('recommendations', [])
        }

    @staticmethod
    def analyze_purchasing_patterns(user=None):
        """Analyze purchasing/expense patterns and provide improvement recommendations."""
        # Kiểm tra data trước khi phân tích
        if user:
            has_data, message = AIService._check_user_has_data(user, 'purchasing')
            if not has_data:
                return {
                    "summary": message,
                    "insights": [],
                    "recommendations": [],
                    "no_data": True
                }
            is_manager = hasattr(user, 'profile') and user.profile.is_manager()
            if is_manager:
                expenses = Expense.objects.all()
                budgets = Budget.objects.all()
            else:
                expenses = Expense.objects.filter(project__created_by=user)
                budgets = Budget.objects.filter(project__created_by=user)
        else:
            # Fallback cho backward compatibility
            expenses = Expense.objects.all()
            budgets = Budget.objects.all()
            
            if not expenses.exists() and not budgets.exists():
                return {
                    "summary": "Chưa có đủ dữ liệu để phân tích mua hàng. Vui lòng tạo ngân sách hoặc chi phí trước.",
                    "insights": [],
                    "recommendations": [],
                    "no_data": True
                }
        
        total_expenses = float(expenses.aggregate(total=Sum('amount'))['total'] or 0)
        
        expenses_by_type = {}
        expenses_by_category = {}
        
        for expense in expenses:
            expense_type = expense.expense_type
            category = expense.category.name
            
            expenses_by_type[expense_type] = float(expenses_by_type.get(expense_type, 0)) + float(expense.amount)
            expenses_by_category[category] = float(expenses_by_category.get(category, 0)) + float(expense.amount)
        
        total_allocated = float(budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0)
        total_spent = float(budgets.aggregate(total=Sum('spent_amount'))['total'] or 0)
        
        context = {
            "purchasing_metrics": {
                "total_expenses": float(total_expenses),
                "total_allocated": float(total_allocated),
                "total_spent": float(total_spent),
                "utilization_rate": (total_spent / total_allocated * 100) if total_allocated > 0 else 0,
                "expenses_by_type": {k: float(v) for k, v in expenses_by_type.items()},
                "expenses_by_category": {k: float(v) for k, v in expenses_by_category.items()},
            }
        }
        
        prompt = (
            "Phân tích hiệu suất mua hàng dựa trên JSON context (tổng chi, phân bổ, theo loại/danh mục, tỉ lệ sử dụng ngân sách).\n"
            "YÊU CẦU:\n"
            "1) Tóm tắt NGẮN GỌN trong 2 đoạn, mỗi đoạn 2-3 câu, nêu trọng tâm.\n"
            "2) Chỉ ra hạng mục/loại chi tiêu nổi bật và rủi ro lãng phí.\n"
            "3) Đề xuất 3-4 hành động tối ưu: cắt/giảm, đàm phán NCC, kiểm soát hạn mức, điều chỉnh phân bổ.\n"
            "4) TRẢ LỜI HOÀN TOÀN BẰNG TIẾNG VIỆT, súc tích.\n"
        )
        
        result = AIService._generate_insight(prompt, context)
        
        insight = AIInsight.objects.create(
            insight_type='purchasing_improvement',
            title="Purchasing Pattern Analysis",
            summary=result.get('summary', ''),
            insights=json.dumps(result.get('insights', [])),
            recommendations=json.dumps(result.get('recommendations', [])),
            context_data=json.dumps(context)
        )
        
        return {
            "insight_id": insight.id,
            "summary": result.get('summary', ''),
            "insights": result.get('insights', []),
            "recommendations": result.get('recommendations', [])
        }

    @staticmethod
    def recommend_expense_optimization(project_id=None, user=None):
        """Analyze expenses and recommend optimal spending patterns with visualizations."""
        from datetime import timedelta
        from django.utils import timezone
        
        # Kiểm tra data trước khi phân tích
        if user:
            has_data, message = AIService._check_user_has_data(user, 'expense')
            if not has_data:
                return {
                    "summary": message,
                    "insights": [],
                    "recommendations": [],
                    "no_data": True,
                    "chart_data": None
                }
            is_manager = hasattr(user, 'profile') and user.profile.is_manager()
            if is_manager:
                expenses = Expense.objects.all()
                budgets = Budget.objects.all()
            else:
                expenses = Expense.objects.filter(project__created_by=user)
                budgets = Budget.objects.filter(project__created_by=user)
        else:
            expenses = Expense.objects.all()
            budgets = Budget.objects.all()
        
        if project_id:
            expenses = expenses.filter(project_id=project_id)
            budgets = budgets.filter(project_id=project_id)
        
        # Kiểm tra lại sau khi filter
        if not expenses.exists():
            return {
                "summary": "Chưa có đủ dữ liệu để tối ưu chi tiêu. Vui lòng tạo chi phí trước.",
                "insights": [],
                "recommendations": [],
                "no_data": True,
                "chart_data": None
            }
        
        # Get last 6 months of expenses
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=180)
        recent_expenses = expenses.filter(expense_date__gte=start_date)
        
        # Calculate monthly spending
        monthly_spending = {}
        for expense in recent_expenses:
            month_key = expense.expense_date.strftime('%Y-%m')
            monthly_spending[month_key] = monthly_spending.get(month_key, 0) + float(expense.amount)
        
        # Calculate spending by category
        spending_by_category = {}
        for expense in recent_expenses:
            category_name = expense.category.name
            spending_by_category[category_name] = spending_by_category.get(category_name, 0) + float(expense.amount)
        
        # Calculate spending by type
        spending_by_type = {}
        for expense in recent_expenses:
            expense_type = expense.get_expense_type_display()
            spending_by_type[expense_type] = spending_by_type.get(expense_type, 0) + float(expense.amount)
        
        
        total_allocated = float(budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0)
        total_spent = float(budgets.aggregate(total=Sum('spent_amount'))['total'] or 0)
        utilization_rate = (total_spent / total_allocated * 100) if total_allocated > 0 else 0
        
        # Identify high spending categories
        avg_category_spending = sum(spending_by_category.values()) / len(spending_by_category) if spending_by_category else 0
        high_spending_categories = {
            cat: amount for cat, amount in spending_by_category.items()
            if amount > avg_category_spending * 1.5
        }
        
        context = {
            "expense_metrics": {
                "total_spent": float(total_spent),
                "total_allocated": float(total_allocated),
                "utilization_rate": float(utilization_rate),
                "monthly_spending": {k: float(v) for k, v in monthly_spending.items()},
                "spending_by_category": {k: float(v) for k, v in spending_by_category.items()},
                "spending_by_type": {k: float(v) for k, v in spending_by_type.items()},
                "high_spending_categories": {k: float(v) for k, v in high_spending_categories.items()},
            }
        }
        
        prompt = """Phân tích chi tiêu tổng thể và đưa ra gợi ý tối ưu hóa chi phí cho doanh nghiệp dịch vụ.
Hãy dựa trên dữ liệu JSON trong phần context (chi tiêu theo tháng, theo danh mục, theo loại, tỉ lệ sử dụng ngân sách).
Yêu cầu:
1. NÊU RÕ các hạng mục chi tiêu nổi bật, nơi đang tiêu tốn nhiều ngân sách.
2. NHẬN ĐỊNH xu hướng chi tiêu theo thời gian (tăng/giảm, mùa vụ,...).
3. ĐỀ XUẤT các hành động cụ thể để tiết kiệm chi phí nhưng vẫn đảm bảo chất lượng dịch vụ.
4. Gợi ý cách phân bổ ngân sách hợp lý hơn giữa các danh mục.
TRẢ LỜI HOÀN TOÀN BẰNG TIẾNG VIỆT."""
        
        result = AIService._generate_insight(prompt, context)

        # Fallback: tự sinh nhận định/đề xuất nếu AI không trả về đủ
        insights = result.get("insights") or []
        recommendations = result.get("recommendations") or []

        if not insights:
            insights = []
            insights.append(
                f"Tổng chi tiêu hiện tại là {float(total_spent):,.0f} VNĐ, tương ứng {float(utilization_rate):.1f}% ngân sách được sử dụng."
            )
            if high_spending_categories:
                top_cat = max(high_spending_categories.items(), key=lambda x: x[1])[0]
                insights.append(
                    f"Danh mục chi tiêu nổi bật cần chú ý là '{top_cat}', có giá trị cao hơn mức trung bình các danh mục khác."
                )
            if monthly_spending:
                values = list(monthly_spending.values())
                trend_up = values[-1] >= values[0]
                latest_month = sorted(monthly_spending.keys())[-1]
                insights.append(
                    f"Chi tiêu tháng {latest_month} có xu hướng {'tăng' if trend_up else 'giảm'} so với đầu kỳ."
                )

        if not recommendations:
            recommendations = []
            if utilization_rate > 90:
                recommendations.append("Xem xét cắt giảm hoặc trì hoãn các khoản chi không cấp thiết để tránh vượt ngân sách.")
            elif utilization_rate < 60:
                recommendations.append("Đánh giá lại kế hoạch ngân sách vì mức sử dụng hiện tại còn thấp so với phân bổ.")
            if high_spending_categories:
                recommendations.append("Thiết lập hạn mức và quy trình duyệt chi chặt chẽ hơn cho các danh mục chi tiêu cao bất thường.")
            recommendations.append("Thiết lập báo cáo chi tiêu theo tháng và cảnh báo sớm khi chi vượt ngưỡng đã cấu hình.")

        result["insights"] = insights
        result["recommendations"] = recommendations
        
        insight = AIInsight.objects.create(
            insight_type='expense_optimization',
            title="Gợi ý Tối ưu Chi tiêu",
            summary=result.get('summary', ''),
            insights=json.dumps(result.get('insights', [])),
            recommendations=json.dumps(result.get('recommendations', [])),
            context_data=json.dumps(context)
        )
        
        return {
            "insight_id": insight.id,
            "summary": result.get('summary', ''),
            "insights": result.get('insights', []),
            "recommendations": result.get('recommendations', []),
            "chart_data": {
                "monthly_spending": monthly_spending,
                "spending_by_category": spending_by_category,
                "spending_by_type": spending_by_type,
            },
            "metrics": {
                "total_spent": float(total_spent),
                "total_allocated": float(total_allocated),
                "utilization_rate": float(utilization_rate),
                "high_spending_categories": {k: float(v) for k, v in high_spending_categories.items()},
            }
        }

    @staticmethod
    def generate_dashboard_insight(user):
        """Tự động generate insight cho dashboard dựa trên dữ liệu hiện tại."""
        # Kiểm tra data trước khi phân tích
        has_data, message = AIService._check_user_has_data(user, 'general')
        if not has_data:
            return {
                "summary": message,
                "insights": [],
                "recommendations": [],
                "no_data": True
            }
        from projects.models import Project, Task
        from resources.models import Employee
        from budgeting.models import Budget, Expense
        from performance.models import PerformanceScore
        
        is_manager = hasattr(user, 'profile') and user.profile.is_manager
        
        # Lấy dữ liệu tổng quan
        if is_manager:
            projects = Project.objects.all()
            employees = Employee.objects.filter(is_active=True)
            budgets = Budget.objects.all()
            expenses = Expense.objects.all()
        else:
            # Nhân viên lấy từ ResourceAllocation
            from resources.models import ResourceAllocation
            employee = getattr(user, 'employee', None)
            if employee:
                allocated_project_ids = ResourceAllocation.objects.filter(
                    employee=employee
                ).values_list('project_id', flat=True).distinct()
                projects = Project.objects.filter(id__in=allocated_project_ids)
                employees = Employee.objects.filter(id=employee.id)  # Chỉ chính mình
                budgets = Budget.objects.filter(project_id__in=allocated_project_ids)
                expenses = Expense.objects.filter(project_id__in=allocated_project_ids)
            else:
                # Nếu không có employee record, trả về empty queryset
                projects = Project.objects.none()
                employees = Employee.objects.none()
                budgets = Budget.objects.none()
                expenses = Expense.objects.none()
        
        # Tính toán metrics
        total_projects = projects.count()
        active_projects = projects.filter(status='active').count()
        total_budget = budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
        total_spent = expenses.aggregate(total=Sum('amount'))['total'] or 0
        total_employees = employees.count()
        
        # Tính completion rate
        completion_rates = []
        for project in projects.filter(status__in=['active', 'completed']):
            tasks = project.tasks.all()
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status='done').count()
            if total_tasks > 0:
                completion_rates.append((completed_tasks / total_tasks) * 100)
        
        avg_completion = sum(completion_rates) / len(completion_rates) if completion_rates else 0
        
        context = {
            "total_projects": total_projects,
            "active_projects": active_projects,
            "total_budget": float(total_budget),
            "total_spent": float(total_spent),
            "total_employees": total_employees,
            "average_completion_rate": round(avg_completion, 1),
        }
        
        prompt = """Phân tích tổng quan hiệu suất dự án và đưa ra insights chi tiết, chuyên sâu.

QUY TẮC NGHIÊM NGẶT - TUÂN THỦ 100%:
1. SUMMARY (3 ĐOẠN, mỗi đoạn 2-3 câu, TỐI ĐA 150 từ TỔNG CỘNG):
   
   ĐOẠN 1 - PHÂN TÍCH CHUYÊN SÂU (50 từ):
   - Phân tích chi tiết kết quả tiến độ dự án dựa trên dữ liệu
   - So sánh tỷ lệ hoàn thành với mục tiêu, đánh giá hiệu quả sử dụng ngân sách
   - Xác định nguyên nhân gốc rễ của các vấn đề về tiến độ
   - Ví dụ: "Phân tích tiến độ cho thấy 6 dự án với 3 dự án đang hoạt động có tỷ lệ hoàn thành trung bình 30.8%, thấp hơn mục tiêu đặt ra. Mức chi tiêu 11.9% ngân sách cho thấy các dự án đang ở giai đoạn đầu hoặc gặp trở ngại trong việc giải ngân."
   
   ĐOẠN 2 - PHƯƠNG ÁN PHÁT TRIỂN (50 từ):
   - Đưa ra các giải pháp cụ thể để cải thiện tiến độ và hiệu quả
   - Tối ưu hóa phân bổ nguồn lực và ngân sách
   - Đề xuất các biện pháp quản lý và giám sát chặt chẽ hơn
   - Ví dụ: "Để cải thiện tình hình, cần đánh giá lại từng dự án để xác định rào cản, tối ưu phân bổ 8 nhân sự cho 3 dự án đang hoạt động, và thiết lập KPI theo dõi tiến độ hàng tuần."
   
   ĐOẠN 3 - DỰ ĐOÁN TƯƠNG LAI (50 từ):
   - Dự đoán xu hướng phát triển của các dự án trong tương lai
   - Đánh giá rủi ro và cơ hội tiềm năng
   - Đưa ra cảnh báo và khuyến nghị dài hạn
   - Ví dụ: "Nếu không có biện pháp can thiệp, các dự án có nguy cơ vượt ngân sách và chậm tiến độ. Tuy nhiên, với việc tối ưu hóa quy trình và tăng cường giám sát, có thể đạt mục tiêu hoàn thành trong 3-6 tháng tới."
   
   - KHÔNG dùng dấu *, **, markdown, JSON, dấu phẩy dư thừa
   - Văn bản thuần túy, mỗi đoạn cách nhau bằng dấu xuống dòng

2. INSIGHTS (3 mục, mỗi mục TỐI ĐA 15 từ):
   - Format BẮT BUỘC: "- [nội dung]" (dấu gạch và khoảng trắng)
   - KHÔNG dùng dấu ngoặc kép, dấu phẩy cuối, dấu chấm cuối
   - Nêu điểm nổi bật về tiến độ, ngân sách, nhân sự
   - Ví dụ: "- Tỷ lệ hoàn thành thấp 30.8% cần cải thiện"

3. RECOMMENDATIONS (3 mục, mỗi mục TỐI ĐA 20 từ):
   - Format BẮT BUỘC: "- [hành động]" (dấu gạch và khoảng trắng)
   - KHÔNG dùng dấu ngoặc kép, dấu phẩy cuối, dấu chấm cuối
   - Hành động cụ thể, có thể thực hiện ngay, tập trung vào cải thiện tiến độ
   - Ví dụ: "- Đánh giá sâu từng dự án để xác định rào cản"

FORMAT OUTPUT (JSON CHÍNH XÁC):
{
  "summary": "Đoạn 1: Phân tích chuyên sâu...\n\nĐoạn 2: Phương án phát triển...\n\nĐoạn 3: Dự đoán tương lai...",
  "insights": ["- Nội dung 1", "- Nội dung 2", "- Nội dung 3"],
  "recommendations": ["- Hành động 1", "- Hành động 2", "- Hành động 3"]
}

LƯU Ý QUAN TRỌNG:
- Summary: 3 ĐOẠN, mỗi đoạn 2-3 câu, TỐI ĐA 150 từ, cách nhau bằng \\n\\n
- Đoạn 1: Phân tích chuyên sâu tiến độ dự án
- Đoạn 2: Phương án phát triển và cải thiện
- Đoạn 3: Dự đoán tương lai và cảnh báo
- Insights: 3 mục, mỗi mục TỐI ĐA 15 từ, BẮT ĐẦU bằng "- "
- Recommendations: 3 mục, mỗi mục TỐI ĐA 20 từ, BẮT ĐẦU bằng "- "
- KHÔNG dùng dấu ngoặc kép, KHÔNG có dấu phẩy cuối"""
        
        result = AIService._generate_insight(prompt, context)
        
        insight = AIInsight.objects.create(
            insight_type='general',
            title="Phân tích Tổng quan Dashboard",
            summary=result.get('summary', ''),
            insights=json.dumps(result.get('insights', [])),
            recommendations=json.dumps(result.get('recommendations', [])),
            context_data=json.dumps(context)
        )
        # Set created_by manually since BaseModel has it
        insight.created_by = user
        insight.save(update_fields=['created_by'])
        
        return insight

    @staticmethod
    def predict_weekly_budget(user, weekly_expenses):
        """Dự đoán budget cho từng tuần dựa trên lịch sử chi tiêu và xu hướng."""
        try:
            # Chuẩn bị context cho AI
            total_expenses = sum(weekly_expenses)
            avg_expense = total_expenses / len(weekly_expenses) if weekly_expenses else 0
            trend = 'increasing' if len(weekly_expenses) >= 2 and weekly_expenses[-1] > weekly_expenses[0] else 'decreasing'
            
            context = {
                "weekly_expenses": weekly_expenses,
                "total_expenses": float(total_expenses),
                "average_expense": float(avg_expense),
                "trend": trend,
                "number_of_weeks": len(weekly_expenses)
            }
            
            prompt = f"""Dựa trên lịch sử chi tiêu 4 tuần gần nhất: {weekly_expenses}
Hãy dự đoán budget hợp lý cho từng tuần trong 4 tuần tiếp theo.
Xu hướng hiện tại: {trend}
Trung bình chi tiêu: {avg_expense:.0f}

Trả về JSON với format:
{{
  "predictions": [budget_tuan1, budget_tuan2, budget_tuan3, budget_tuan4],
  "reasoning": "Lý do dự đoán"
}}

Lưu ý: Budget nên phản ánh xu hướng thực tế và có tính thực tế."""
            
            result = AIService._generate_insight(prompt, context)
            
            # Parse predictions từ AI response
            predictions = result.get('recommendations', [])
            if isinstance(predictions, list) and len(predictions) >= 4:
                # Nếu AI trả về recommendations dạng text, parse số
                try:
                    predicted_budgets = []
                    for pred in predictions[:4]:
                        # Extract số từ text
                        import re
                        numbers = re.findall(r'\d+\.?\d*', str(pred))
                        if numbers:
                            predicted_budgets.append(float(numbers[0]))
                        else:
                            predicted_budgets.append(float(avg_expense))
                    return predicted_budgets
                except:
                    pass
            
            # Fallback: Sử dụng moving average với trend adjustment
            if len(weekly_expenses) >= 2:
                # Tính moving average
                recent_avg = sum(weekly_expenses[-2:]) / 2
                # Điều chỉnh theo trend
                if trend == 'increasing':
                    adjustment = 1.1  # Tăng 10%
                else:
                    adjustment = 0.95  # Giảm 5%
                
                base_budget = recent_avg * adjustment
                # Tạo 4 tuần với biến thể nhỏ
                predicted_budgets = [
                    base_budget * 0.95,
                    base_budget,
                    base_budget * 1.05,
                    base_budget * 1.02
                ]
            else:
                # Nếu không đủ data, dùng giá trị trung bình
                predicted_budgets = [float(avg_expense)] * 4
            
            return predicted_budgets
            
        except Exception as e:
            # Fallback: Trả về giá trị trung bình
            avg = sum(weekly_expenses) / len(weekly_expenses) if weekly_expenses else 0
            return [float(avg)] * 4

    @staticmethod
    def recommend_personnel_for_project(context):
        """
        Đề xuất nhân sự cho dự án sử dụng AI.
        
        Args:
            context: dict chứa thông tin dự án và nhân sự khả dụng
        
        Returns:
            dict: {
                'recommendations': list,
                'reasoning': str,
                'total_cost': float
            }
        """
        try:
            project_name = context.get('project_name', 'Dự án')
            project_description = context.get('project_description', '')
            budget = context.get('budget_for_personnel', 0)
            required_departments = context.get('required_departments', [])
            optimization_goal = context.get('optimization_goal', 'balanced')
            employees = context.get('available_employees', [])
            
            goal_text = {
                'performance': 'tối ưu hiệu suất',
                'cost': 'tối ưu chi phí',
                'balanced': 'cân bằng giữa hiệu suất và chi phí'
            }.get(optimization_goal, 'cân bằng')
            
            prompt = f"""Bạn là chuyên gia tư vấn nhân sự cho dự án.

Dự án: {project_name}
Mô tả: {project_description}
Ngân sách nhân sự: {budget:,.0f} VNĐ
Phòng ban yêu cầu: {', '.join(required_departments) if required_departments else 'Không yêu cầu cụ thể'}
Mục tiêu: {goal_text}

Danh sách nhân sự khả dụng:
{json.dumps(employees, ensure_ascii=False, indent=2)}

Hãy đề xuất nhân sự phù hợp cho dự án này với các tiêu chí:
1. Phù hợp với phòng ban yêu cầu
2. {goal_text.capitalize()}
3. Trong phạm vi ngân sách
4. Tỷ lệ phân bổ hợp lý (tổng không quá 100% cho mỗi người)

Trả về JSON với format:
{{
  "recommendations": [
    {{
      "employee_id": id,
      "allocation_percentage": số phần trăm (0-100),
      "estimated_hours": số giờ ước tính,
      "reasoning": "Lý do đề xuất nhân sự này"
    }}
  ],
  "reasoning": "Tổng quan về đề xuất và lý do",
  "total_cost": tổng chi phí ước tính
}}

Lưu ý:
- Tổng allocation_percentage của tất cả nhân sự không nên vượt quá 300% (3 người full-time)
- Ưu tiên nhân sự có điểm hiệu suất cao nếu mục tiêu là performance
- Ưu tiên nhân sự có chi phí thấp nếu mục tiêu là cost
- Cân bằng cả hai nếu mục tiêu là balanced"""
            
            result = AIService._generate_insight(prompt, {})
            
            # Parse kết quả
            if isinstance(result, dict):
                recommendations = result.get('recommendations', [])
                reasoning = result.get('reasoning', 'Đề xuất từ AI')
                total_cost = result.get('total_cost', 0)
                
                # Map employee_id về Employee objects
                employee_map = {emp['id']: emp for emp in employees}
                final_recommendations = []
                
                for rec in recommendations:
                    emp_id = rec.get('employee_id')
                    if emp_id in employee_map:
                        emp_data = employee_map[emp_id]
                        # Tìm Employee object
                        try:
                            employee = Employee.objects.get(id=emp_id)
                            # Tính estimated_cost
                            from resources.salary_services import HourlyRateService
                            from projects.personnel_services import PersonnelRecommendationService
                            estimated_hours = Decimal(str(rec.get('estimated_hours', 160)))
                            allocation = Decimal(str(rec.get('allocation_percentage', 100)))
                            estimated_cost = PersonnelRecommendationService.calculate_employee_cost(
                                employee, estimated_hours, allocation
                            )
                            
                            final_recommendations.append({
                                'employee': employee,
                                'allocation_percentage': allocation,
                                'estimated_hours': estimated_hours,
                                'estimated_cost': estimated_cost,
                                'reasoning': rec.get('reasoning', ''),
                                'performance_score': emp_data.get('performance_score', 0),
                            })
                        except Employee.DoesNotExist:
                            continue
                
                return {
                    'recommendations': final_recommendations,
                    'reasoning': reasoning,
                    'total_cost': Decimal(str(total_cost))
                }
            
            return None
            
        except Exception as e:
            # Fallback về None để service gọi rule-based
            return None