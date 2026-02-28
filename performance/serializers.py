from rest_framework import serializers
from .models import PerformanceMetric, PerformanceScore


class PerformanceMetricSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceMetric
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else None

    def get_project_name(self, obj):
        return obj.project.name if obj.project else None


class PerformanceScoreSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceScore
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else None

    def get_project_name(self, obj):
        return obj.project.name if obj.project else None

