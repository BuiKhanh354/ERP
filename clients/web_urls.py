"""Web URL patterns for Client Management."""
from django.urls import path
from .web_views import (
    ClientListView, ClientDetailView, ClientCreateView,
    ClientUpdateView, ClientDeleteView, ContactCreateView,
    InteractionCreateView
)

app_name = 'clients'

urlpatterns = [
    path('', ClientListView.as_view(), name='list'),
    path('<int:pk>/', ClientDetailView.as_view(), name='detail'),
    path('create/', ClientCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', ClientUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', ClientDeleteView.as_view(), name='delete'),
    path('<int:client_id>/contact/create/', ContactCreateView.as_view(), name='contact-create'),
    path('<int:client_id>/interaction/create/', InteractionCreateView.as_view(), name='interaction-create'),
]
