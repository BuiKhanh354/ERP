from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, ContactViewSet, ClientInteractionViewSet

router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'contacts', ContactViewSet, basename='contact')
router.register(r'interactions', ClientInteractionViewSet, basename='interaction')

urlpatterns = [
    # API routes
    path('', include(router.urls)),
]

