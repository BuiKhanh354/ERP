from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BudgetCategoryViewSet, BudgetViewSet, ExpenseViewSet
from .web_views import (
    BudgetListView, BudgetDetailView, BudgetCreateView,
    BudgetUpdateView, BudgetDeleteView, ExpenseCreateView, CreateBudgetCategoryView
)

# API routes
router = DefaultRouter()
router.register(r'categories', BudgetCategoryViewSet, basename='category')
router.register(r'budgets', BudgetViewSet, basename='budget')
router.register(r'expenses', ExpenseViewSet, basename='expense')

urlpatterns = [
    # Web routes - Đặt các route cụ thể trước route có parameter và API routes
    path('list/', BudgetListView.as_view(), name='list'),
    path('create/', BudgetCreateView.as_view(), name='create'),
    path('expenses/create/', ExpenseCreateView.as_view(), name='expense_create'),
    path('api/create-category/', CreateBudgetCategoryView.as_view(), name='create_category'),
    
    # Routes với parameter phải đặt sau các route cụ thể
    path('<int:pk>/', BudgetDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', BudgetUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', BudgetDeleteView.as_view(), name='delete'),
    
    # API routes - Đặt cuối cùng để tránh conflict với web routes
    path('', include(router.urls)),
]
