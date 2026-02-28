from django.db import models
from core.models import BaseModel


class Client(BaseModel):
    """Client model for CRM functionality."""
    CLIENT_TYPE_CHOICES = [
        ('individual', 'Cá nhân'),
        ('company', 'Công ty'),
        ('government', 'Chính phủ'),
    ]

    STATUS_CHOICES = [
        ('active', 'Đang hoạt động'),
        ('inactive', 'Không hoạt động'),
        ('prospect', 'Tiềm năng'),
    ]

    name = models.CharField(max_length=200)
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPE_CHOICES, default='company')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='prospect')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Contact(BaseModel):
    """Contact person for clients."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contacts')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    position = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['client', 'is_primary', 'last_name']
        unique_together = ['client', 'email']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.client.name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class ClientInteraction(BaseModel):
    """Interaction history with clients."""
    INTERACTION_TYPE_CHOICES = [
        ('meeting', 'Cuộc họp'),
        ('call', 'Cuộc gọi'),
        ('email', 'Email'),
        ('proposal', 'Đề xuất'),
        ('contract', 'Hợp đồng'),
        ('other', 'Khác'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='interactions')
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPE_CHOICES)
    date = models.DateTimeField()
    subject = models.CharField(max_length=200)
    description = models.TextField()
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.client.name} - {self.interaction_type} - {self.date}"

