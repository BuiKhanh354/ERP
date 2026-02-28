from rest_framework import serializers
import json
from .models import AIInsight


class AIInsightSerializer(serializers.ModelSerializer):
    insights_list = serializers.SerializerMethodField()
    recommendations_list = serializers.SerializerMethodField()

    class Meta:
        model = AIInsight
        fields = ['id', 'insight_type', 'title', 'summary', 'insights_list', 'recommendations_list', 'created_at']
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_insights_list(self, obj):
        try:
            return json.loads(obj.insights) if obj.insights else []
        except:
            return []

    def get_recommendations_list(self, obj):
        try:
            return json.loads(obj.recommendations) if obj.recommendations else []
        except:
            return []

