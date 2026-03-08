"""Models for the Accounting module."""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from core.models import BaseModel


class Invoice(BaseModel):
    """Invoice model for billing clients."""

    STATUS_CHOICES = [
        ('draft', 'Nháp'),
        ('sent', 'Đã gửi'),
        ('paid', 'Đã thanh toán'),
        ('overdue', 'Quá hạn'),
    ]

    REGION_CHOICES = [
        ('mb', 'Miền Bắc'),
        ('mt', 'Miền Trung'),
        ('mn', 'Miền Nam'),
        ('global', 'Quốc tế'),
    ]

    SALES_CHANNEL_CHOICES = [
        ('direct', 'Trực tiếp'),
        ('partner', 'Đối tác/Đại lý'),
        ('online', 'Trực tuyến'),
    ]

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='invoices'
    )
    client = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE, related_name='invoices'
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    
    # Revenue Analytics Fields
    region = models.CharField(max_length=20, choices=REGION_CHOICES, default='mb', help_text='Vùng kinh doanh')
    sales_channel = models.CharField(max_length=20, choices=SALES_CHANNEL_CHOICES, default='direct', help_text='Kênh bán hàng')
    product_category = models.CharField(max_length=100, blank=True, help_text='Danh mục sản phẩm/dịch vụ')
    issue_date = models.DateField()
    due_date = models.DateField()
    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    tax = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Phần trăm thuế (%)', validators=[MinValueValidator(0)]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-issue_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['project', 'status']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.client.name}"

    @property
    def subtotal(self):
        """Tổng tiền trước thuế (sum of invoice items)."""
        return sum(item.total for item in self.items.all())

    @property
    def tax_amount(self):
        """Số tiền thuế."""
        return self.subtotal * self.tax / 100

    @property
    def grand_total(self):
        """Tổng tiền sau thuế."""
        return self.subtotal + self.tax_amount

    @property
    def amount_paid(self):
        """Tổng số tiền đã thanh toán."""
        return sum(p.amount for p in self.payments.all())

    @property
    def amount_due(self):
        """Số tiền còn phải thanh toán."""
        return self.total_amount - self.amount_paid

    def recalculate_total(self):
        """Tính lại total_amount từ items + tax."""
        self.total_amount = self.grand_total
        self.save(update_fields=['total_amount', 'updated_at'])


class InvoiceItem(BaseModel):
    """Line items for an invoice."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='items'
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0.01)]
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.description} (x{self.quantity})"

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Payment(BaseModel):
    """Payment records for invoices."""

    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Chuyển khoản'),
        ('cash', 'Tiền mặt'),
        ('credit_card', 'Thẻ tín dụng'),
        ('online', 'Thanh toán online'),
    ]

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default='bank_transfer'
    )
    payment_date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True, default='')
    note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.invoice_number}"


class VendorBill(BaseModel):
    """Vendor Bill model for Accounts Payable."""

    STATUS_CHOICES = [
        ('draft', 'Nháp'),
        ('received', 'Đã nhận'),
        ('paid', 'Đã thanh toán'),
        ('overdue', 'Quá hạn'),
    ]

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='vendor_bills', null=True, blank=True
    )
    vendor_name = models.CharField(max_length=255)
    bill_number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField()
    due_date = models.DateField()
    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    tax = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text='Phần trăm thuế (%)', validators=[MinValueValidator(0)]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-issue_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"{self.bill_number} - {self.vendor_name}"

    @property
    def subtotal(self):
        return sum(item.total for item in self.items.all())

    @property
    def tax_amount(self):
        return self.subtotal * self.tax / 100

    @property
    def grand_total(self):
        return self.subtotal + self.tax_amount

    @property
    def amount_paid(self):
        return sum(p.amount for p in self.payments.all())

    @property
    def amount_due(self):
        return self.total_amount - self.amount_paid

    def recalculate_total(self):
        self.total_amount = self.grand_total
        self.save(update_fields=['total_amount', 'updated_at'])


class VendorBillItem(BaseModel):
    """Line items for a vendor bill."""

    bill = models.ForeignKey(
        VendorBill, on_delete=models.CASCADE, related_name='items'
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(0.01)]
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.description} (x{self.quantity})"

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class VendorPayment(BaseModel):
    """Payment records for vendor bills."""

    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Chuyển khoản'),
        ('cash', 'Tiền mặt'),
        ('credit_card', 'Thẻ tín dụng'),
        ('online', 'Thanh toán online'),
    ]

    bill = models.ForeignKey(
        VendorBill, on_delete=models.CASCADE, related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default='bank_transfer'
    )
    payment_date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True, default='')
    note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"Payment {self.amount} for {self.bill.bill_number}"
