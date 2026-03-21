from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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


def _clean_roles(user) -> set[str]:
    roles = set()
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "role", None):
        roles.add(str(profile.role).lower())
    for group in user.groups.all():
        roles.add(str(group.name).lower())
    if user.is_superuser:
        roles.add("superuser")
    if user.is_staff:
        roles.add("staff")
    return roles


def _can_access(user, capability: str) -> bool:
    roles = _clean_roles(user)
    if {"superuser", "staff"} & roles:
        return True
    if capability == "chat":
        return True
    if "manager" in roles:
        return True
    if capability == "attrition" and {"hr", "hr_admin"} & roles:
        return True
    if capability in {"forecast", "anomaly"} and {"cfo", "finance", "finance_admin", "executive"} & roles:
        return True
    if capability in {"recommend", "risk", "report"} and {"pm", "project_manager", "resource_manager", "executive", "cfo"} & roles:
        return True
    return False


def _require_access(user, capability: str) -> Response | None:
    if _can_access(user, capability):
        return None
    return Response(
        {"detail": "Bạn không có quyền truy cập chức năng này."},
        status=status.HTTP_403_FORBIDDEN,
    )


class ChatAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        denied = _require_access(request.user, "chat")
        if denied:
            return denied

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "message is required."}, status=status.HTTP_400_BAD_REQUEST)

        project_id = request.data.get("project_id")
        employee_id = request.data.get("employee_id")
        context = build_chat_context(message=message, project_id=project_id, employee_id=employee_id)
        result = answer_chat(message=message, role=getattr(getattr(request.user, "profile", None), "role", None), context=context)
        return Response(result, status=status.HTTP_200_OK)


class AttritionPredictAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        denied = _require_access(request.user, "attrition")
        if denied:
            return denied

        payload: dict[str, Any] = request.data.get("features") or request.data
        if "features" in payload:
            payload = payload["features"]

        try:
            result = predict_attrition(payload)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class RevenueForecastAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_access(request.user, "forecast")
        if denied:
            return denied

        periods = int(request.query_params.get("periods", 4))
        history = request.query_params.getlist("history")
        result = forecast_revenue(periods=periods, history=[float(item) for item in history] if history else None)
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request):
        denied = _require_access(request.user, "forecast")
        if denied:
            return denied

        periods = int(request.data.get("periods", 4))
        history = request.data.get("history")
        result = forecast_revenue(periods=periods, history=history)
        return Response(result, status=status.HTTP_200_OK)


class AnomalyDetectionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_access(request.user, "anomaly")
        if denied:
            return denied

        project_id = request.query_params.get("project_id")
        history = request.query_params.getlist("values")
        result = detect_anomalies(
            values=[float(item) for item in history] if history else None,
            project_id=int(project_id) if project_id else None,
        )
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request):
        denied = _require_access(request.user, "anomaly")
        if denied:
            return denied

        result = detect_anomalies(
            values=request.data.get("values"),
            project_id=request.data.get("project_id"),
        )
        return Response(result, status=status.HTTP_200_OK)


class ResourceRecommendationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        denied = _require_access(request.user, "recommend")
        if denied:
            return denied

        result = recommend_resources(
            project_id=request.data.get("project_id"),
            required_departments=request.data.get("required_departments"),
            required_skills=request.data.get("required_skills"),
            hours_needed=request.data.get("hours_needed", 40),
        )
        return Response(result, status=status.HTTP_200_OK)


class RiskDetectionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_access(request.user, "risk")
        if denied:
            return denied

        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = detect_project_risks(int(project_id))
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ProjectSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_access(request.user, "report")
        if denied:
            return denied

        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = summarize_project(int(project_id))
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
