from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, EmployeeViewSet, ResourceAllocationViewSet

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'allocations', ResourceAllocationViewSet, basename='allocation')

urlpatterns = [
    path('', include(router.urls)),
]

