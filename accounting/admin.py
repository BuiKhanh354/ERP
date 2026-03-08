"""Admin configuration for the Accounting module."""
from django.contrib import admin
from .models import Invoice, InvoiceItem, Payment


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'project', 'client', 'total_amount', 'status', 'issue_date', 'due_date']
    list_filter = ['status', 'issue_date', 'project']
    search_fields = ['invoice_number', 'client__name', 'project__name']
    inlines = [InvoiceItemInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'payment_method', 'payment_date', 'reference_number']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['invoice__invoice_number', 'reference_number']
    readonly_fields = ['created_at', 'updated_at']
