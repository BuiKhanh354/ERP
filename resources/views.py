from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Department, Employee, ResourceAllocation
from .serializers import DepartmentSerializer, EmployeeSerializer, ResourceAllocationSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]


class ResourceAllocationViewSet(viewsets.ModelViewSet):
    queryset = ResourceAllocation.objects.all()
    serializer_class = ResourceAllocationSerializer
    permission_classes = [IsAuthenticated]

