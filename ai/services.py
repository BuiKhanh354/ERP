"""Compatibility AI service without cloud AI dependencies."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .mini_ai_service import (
    answer_chat,
    build_chat_context,
    detect_anomalies,
    detect_project_risks,
    forecast_revenue,
    predict_attrition,
    recommend_resources,
    summarize_project,
)


def _disabled_response(message: str = "Feature temporarily disabled to refactor AI") -> dict[str, Any]:
    return {
        "message": message,
        "status": 501,
        "no_data": True,
        "insights": [],
        "recommendations": [],
    }


class AIService:
    """Backward-compatible AI service facade without cloud AI usage."""

    @staticmethod
    def analyze_resource_performance(employee_id):
        return _disabled_response()

    @staticmethod
    def recommend_project_staffing(project_id):
        return _disabled_response()

    @staticmethod
    def analyze_budget_patterns(project_id):
        return _disabled_response()

    @staticmethod
    def analyze_sales_performance(user=None):
        return _disabled_response()

    @staticmethod
    def analyze_purchasing_patterns(user=None):
        return _disabled_response()

    @staticmethod
    def recommend_expense_optimization(project_id=None, user=None):
        return _disabled_response()

    @staticmethod
    def generate_dashboard_insight(user):
        return _disabled_response()

    @staticmethod
    def predict_weekly_budget(user, weekly_expenses):
        avg = sum(weekly_expenses) / len(weekly_expenses) if weekly_expenses else 0
        return [float(avg)] * 4

    @staticmethod
    def recommend_personnel_for_project(context):
        return None

    @staticmethod
    def recommend_personnel(project, optimization_goal='balanced', use_ai=True):
        return None

    @staticmethod
    def build_chat_context(*args, **kwargs):
        return build_chat_context(*args, **kwargs)

    @staticmethod
    def answer_chat(*args, **kwargs):
        return answer_chat(*args, **kwargs)

    @staticmethod
    def predict_attrition(*args, **kwargs):
        return predict_attrition(*args, **kwargs)

    @staticmethod
    def forecast_revenue(*args, **kwargs):
        return forecast_revenue(*args, **kwargs)

    @staticmethod
    def detect_anomalies(*args, **kwargs):
        return detect_anomalies(*args, **kwargs)

    @staticmethod
    def recommend_resources(*args, **kwargs):
        return recommend_resources(*args, **kwargs)

    @staticmethod
    def detect_project_risks(*args, **kwargs):
        return detect_project_risks(*args, **kwargs)

    @staticmethod
    def summarize_project(*args, **kwargs):
        return summarize_project(*args, **kwargs)
