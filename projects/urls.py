from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, TaskViewSet, TimeEntryViewSet
from .web_views import (
    ProjectListView, ProjectDetailView, ProjectCreateView,
    ProjectUpdateView, ProjectDeleteView,
    ProjectAddPersonnelView,
    BudgetMonitoringView
)
from .task_views import (
    TaskListView, TaskCreateView, TaskUpdateView, TaskDeleteView, 
    TaskUpdateStatusView, GetEmployeesByDepartmentView, MyTasksView,
    UpdateAssignmentStatusView, PhaseDateSuggestionView
)
from .time_entry_views import (
    TimeEntryCreateView, MyTimeEntriesView, QuickLogTimeEntryView,
    AutoLogTimeOnCompleteView
)
from .phase_views import (
    PhaseCreateView, PhaseUpdateView, PhaseDeleteView,
    PhaseReorderAPIView, GanttDataAPIView, TaskProgressUpdateView
)
from .delay_views import (
    DelayKPIDashboardView, DelayKPIDataAPIView, DelayKPIExportCSVView,
    MyDelayHistoryAPIView, KPIAdjustmentRequestCreateView, KPIAdjustmentRequestReviewView
)
from core.role_views.pm_views import PMRequestMemberView, PMMemberApprovalView

# API routes
router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'time-entries', TimeEntryViewSet, basename='time-entry')

# Web routes
urlpatterns = [
    # API
    path('api/', include(router.urls)),
    
    # Web views
    path('', ProjectListView.as_view(), name='list'),
    path('create/', ProjectCreateView.as_view(), name='create'),
    path('<int:pk>/', ProjectDetailView.as_view(), name='detail'),
    path('<int:project_id>/add-personnel/', ProjectAddPersonnelView.as_view(), name='add_personnel'),
    path('<int:pk>/edit/', ProjectUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', ProjectDeleteView.as_view(), name='delete'),
    
    # Phases
    path('<int:project_id>/phases/create/', PhaseCreateView.as_view(), name='phase_create'),
    path('phases/<int:pk>/edit/', PhaseUpdateView.as_view(), name='phase_edit'),
    path('phases/<int:pk>/delete/', PhaseDeleteView.as_view(), name='phase_delete'),
    path('api/phases/reorder/', PhaseReorderAPIView.as_view(), name='phase_reorder'),
    
    # Gantt & Progress
    path('<int:project_id>/gantt-data/', GanttDataAPIView.as_view(), name='gantt_data'),
    path('api/tasks/<int:pk>/progress/', TaskProgressUpdateView.as_view(), name='task_progress_update'),
    
    # Tasks
    path('tasks/', TaskListView.as_view(), name='tasks'),
    path('tasks/my-tasks/', MyTasksView.as_view(), name='my_tasks'),
    path('tasks/create/', TaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/edit/', TaskUpdateView.as_view(), name='task_edit'),
    path('tasks/<int:pk>/delete/', TaskDeleteView.as_view(), name='task_delete'),
    path('tasks/<int:pk>/update-status/', TaskUpdateStatusView.as_view(), name='task_update_status'),
    path('tasks/<int:pk>/update-assignment-status/', UpdateAssignmentStatusView.as_view(), name='update_assignment_status'),
    path('api/get-employees-by-department/', GetEmployeesByDepartmentView.as_view(), name='get_employees_by_department'),
    path('api/phase-date-suggestion/', PhaseDateSuggestionView.as_view(), name='phase_date_suggestion'),
    
    # Time Entries
    path('time-entries/create/', TimeEntryCreateView.as_view(), name='time_entry_create'),
    path('time-entries/my-entries/', MyTimeEntriesView.as_view(), name='my_time_entries'),
    path('tasks/<int:task_id>/quick-log-time/', QuickLogTimeEntryView.as_view(), name='quick_log_time'),
    path('tasks/<int:task_id>/auto-log-time/', AutoLogTimeOnCompleteView.as_view(), name='auto_log_time'),
    
    # Personnel recommendation module removed in compact mode
    path('<int:project_id>/budget-monitoring/', BudgetMonitoringView.as_view(), name='budget_monitoring'),
    path('<int:project_id>/request-member/', PMRequestMemberView.as_view(), name='request_member'),
    path('<int:project_id>/member-approval/', PMMemberApprovalView.as_view(), name='member_approval'),
    path('delay-kpi/dashboard/', DelayKPIDashboardView.as_view(), name='delay_kpi_dashboard'),
    path('api/delay-kpi/', DelayKPIDataAPIView.as_view(), name='delay_kpi_data'),
    path('api/delay-kpi/export-csv/', DelayKPIExportCSVView.as_view(), name='delay_kpi_export_csv'),
    path('api/delay-kpi/my-history/', MyDelayHistoryAPIView.as_view(), name='delay_kpi_my_history'),
    path('delay-kpi/adjustments/create/', KPIAdjustmentRequestCreateView.as_view(), name='delay_kpi_adjustment_create'),
    path('delay-kpi/adjustments/<int:pk>/review/', KPIAdjustmentRequestReviewView.as_view(), name='delay_kpi_adjustment_review'),
]


