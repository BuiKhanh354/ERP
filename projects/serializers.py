from rest_framework import serializers
from .models import Project, Task, TimeEntry


class ProjectSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.full_name
        return None


class TimeEntrySerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    task_name = serializers.CharField(source='task.name', read_only=True)

    class Meta:
        model = TimeEntry
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else None

