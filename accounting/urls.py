"""URL configuration for the Accounting module."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, PaymentViewSet
from .web_views import (
    AccountingDashboardView,
    InvoiceListView, InvoiceDetailView, InvoiceCreateView,
    InvoiceUpdateView, InvoiceDeleteView, InvoiceMarkPaidView,
    ExpenseListView, ExpenseCreateView, ExpenseUpdateView, ExpenseDeleteView,
    PaymentListView, PaymentCreateView, PaymentUpdateView,
    BudgetSummaryView,
    ReportListView, ReportExportView,
)

# API routes
router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    # Dashboard
    path('', AccountingDashboardView.as_view(), name='dashboard'),

    # Invoice web routes
    path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/edit/', InvoiceUpdateView.as_view(), name='invoice_edit'),
    path('invoices/<int:pk>/delete/', InvoiceDeleteView.as_view(), name='invoice_delete'),
    path('invoices/<int:pk>/mark-paid/', InvoiceMarkPaidView.as_view(), name='invoice_mark_paid'),

    # Expense web routes
    path('expenses/', ExpenseListView.as_view(), name='expense_list'),
    path('expenses/create/', ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/edit/', ExpenseUpdateView.as_view(), name='expense_edit'),
    path('expenses/<int:pk>/delete/', ExpenseDeleteView.as_view(), name='expense_delete'),

    # Payment web routes
    path('payments/', PaymentListView.as_view(), name='payment_list'),
    path('payments/create/', PaymentCreateView.as_view(), name='payment_create'),
    path('payments/<int:pk>/edit/', PaymentUpdateView.as_view(), name='payment_edit'),

    # Budget summary
    path('budget/', BudgetSummaryView.as_view(), name='budget_summary'),

    # Reports
    path('reports/', ReportListView.as_view(), name='reports'),
    path('reports/export/', ReportExportView.as_view(), name='report_export'),

    # API routes
    path('api/', include(router.urls)),
]
