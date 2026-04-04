from rest_framework import serializers
from .models import Project, Task, TimeEntry, ProjectPhase, TaskProgressLog


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
    phase_name = serializers.CharField(source='phase.phase_name', read_only=True, default=None)

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.full_name
        return None

    def validate(self, attrs):
        project = attrs.get('project') or getattr(self.instance, 'project', None)
        name = attrs.get('name', getattr(self.instance, 'name', ''))
        if isinstance(name, str):
            name = name.strip()
            attrs['name'] = name

        if project and name:
            duplicate_qs = Task.objects.filter(project=project, name__iexact=name)
            if self.instance and self.instance.pk:
                duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
            if duplicate_qs.exists():
                raise serializers.ValidationError({
                    'name': 'Tên công việc đã tồn tại trong dự án này. Vui lòng đặt tên khác.'
                })

        priority = attrs.get('priority', getattr(self.instance, 'priority', 'medium'))
        assigned_to = attrs.get('assigned_to', getattr(self.instance, 'assigned_to', None))
        if priority == 'critical' and assigned_to and assigned_to.kpi_current < 70:
            raise serializers.ValidationError({
                'assigned_to': 'Nhan su duoc giao task critical phai co KPI >= 70.'
            })

        return attrs


class TimeEntrySerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    task_name = serializers.CharField(source='task.name', read_only=True)

    class Meta:
        model = TimeEntry
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else None


class ProjectPhaseSerializer(serializers.ModelSerializer):
    """Serializer cho ProjectPhase."""
    calculated_progress = serializers.FloatField(read_only=True)
    task_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProjectPhase
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class TaskProgressLogSerializer(serializers.ModelSerializer):
    """Serializer cho TaskProgressLog."""
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskProgressLog
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username if obj.user else None


