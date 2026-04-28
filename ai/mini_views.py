from __future__ import annotations

from typing import Any

from django.db import ProgrammingError, OperationalError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.rbac import get_user_role_names
from core.rbac import get_client_ip
from projects.models import Task
from resources.models import Employee
from .audit import log_ai_usage, start_timer
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


def _build_attrition_features_from_employee(employee_id: int) -> dict[str, Any]:
    employee = Employee.objects.filter(pk=employee_id).first()
    if not employee:
        raise ValueError(f"Employee {employee_id} not found.")

    today = timezone.localdate()
    years_at_company = 0
    if employee.hire_date:
        years_at_company = max(0, int((today - employee.hire_date).days / 365.25))

    # Heuristic mapping for demo when full HR survey features are unavailable.
    job_level_map = {
        "intern": 1,
        "part_time": 1,
        "contractor": 2,
        "full_time": 3,
    }
    job_level = job_level_map.get(str(employee.employment_type or "").lower(), 2)
    monthly_income = float(employee.hourly_rate or 0) * 160.0

    all_tasks = Task.objects.filter(assigned_to=employee).count()
    overdue_open_tasks = Task.objects.filter(
        assigned_to=employee,
        due_date__lt=today,
    ).exclude(status="completed").count()

    overtime_flag = "Yes" if overdue_open_tasks >= 2 else "No"
    kpi = float(employee.kpi_current or 100.0)
    job_satisfaction = 4 if kpi >= 90 else 3 if kpi >= 75 else 2 if kpi >= 60 else 1
    total_working_years = max(years_at_company + 2, years_at_company)

    age_estimate = 30
    if years_at_company >= 10:
        age_estimate = 40
    elif years_at_company >= 5:
        age_estimate = 35
    elif years_at_company <= 1:
        age_estimate = 25

    return {
        "Age": age_estimate,
        "JobLevel": job_level,
        "MonthlyIncome": round(monthly_income, 2),
        "TotalWorkingYears": total_working_years,
        "YearsAtCompany": years_at_company,
        "JobSatisfaction": job_satisfaction,
        "OverTime": overtime_flag,
        "_meta": {
            "employee_id": employee.id,
            "employee_name": employee.full_name,
            "tasks_total": all_tasks,
            "overdue_open_tasks": overdue_open_tasks,
        },
    }


def _clean_roles(user) -> set[str]:
    roles = set()
    # RBAC v2 roles
    try:
        roles.update({str(r).lower() for r in get_user_role_names(user)})
    except Exception:
        pass

    # Legacy profile/group fallback
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "role", None):
        roles.add(str(profile.role).lower())
    try:
        for group in user.groups.all():
            roles.add(str(group.name).lower())
    except (ProgrammingError, OperationalError):
        # Some compact DBs may not include auth_group/auth_user_groups tables.
        # RBAC v2 roles from UserRole still work, so we safely skip legacy groups.
        pass
    if user.is_superuser:
        roles.add("superuser")
    if user.is_staff:
        roles.add("staff")
    return roles


def _can_access(user, capability: str) -> bool:
    roles = _clean_roles(user)
    if {"superuser", "staff"} & roles:
        return True
    if "admin" in roles:
        return True
    if capability == "chat":
        return True
    if "manager" in roles:
        return True
    if capability == "attrition" and {"hr", "hr_admin", "manager", "admin"} & roles:
        return True
    if capability in {"forecast", "anomaly"} and {"cfo", "finance", "finance_admin", "executive", "admin"} & roles:
        return True
    if capability in {"recommend", "risk", "report"} and {"pm", "project_manager", "resource_manager", "executive", "cfo", "manager", "admin"} & roles:
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
        started = start_timer()
        denied = _require_access(request.user, "chat")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/chat/",
                request_payload={"message": request.data.get("message", "")},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        message = (request.data.get("message") or "").strip()
        if not message:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/chat/",
                request_payload={"message": ""},
                response_payload={"detail": "message is required."},
                status_code=400,
                source="validation",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response({"detail": "message is required."}, status=status.HTTP_400_BAD_REQUEST)

        project_id = request.data.get("project_id")
        employee_id = request.data.get("employee_id")
        context = build_chat_context(message=message, project_id=project_id, employee_id=employee_id)
        result = answer_chat(message=message, role=getattr(getattr(request.user, "profile", None), "role", None), context=context)
        log_ai_usage(
            user=request.user,
            endpoint="/api/ai/chat/",
            request_payload={"message": message[:250], "project_id": project_id, "employee_id": employee_id},
            response_payload={"source": result.get("source", ""), "has_answer": bool(result.get("answer"))},
            status_code=200,
            source=result.get("source", ""),
            fallback_used=result.get("source", "") == "fallback",
            ip_address=get_client_ip(request),
            started_at=started,
        )
        return Response(result, status=status.HTTP_200_OK)


class AttritionPredictAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        started = start_timer()
        denied = _require_access(request.user, "attrition")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/predict-attrition/",
                request_payload={"detail": "forbidden"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        raw_payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        payload: dict[str, Any] = raw_payload.get("features") or raw_payload
        if "features" in payload:
            payload = payload["features"]
        employee_id = raw_payload.get("employee_id")
        if employee_id and not all(k in payload for k in ("Age", "JobLevel", "MonthlyIncome", "TotalWorkingYears", "YearsAtCompany", "JobSatisfaction", "OverTime")):
            built = _build_attrition_features_from_employee(int(employee_id))
            payload = {k: v for k, v in built.items() if not str(k).startswith("_")}

        try:
            result = predict_attrition(payload)
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/predict-attrition/",
                request_payload={"feature_keys": sorted(list(payload.keys()))[:20]},
                response_payload={"level": result.get("level"), "attrition_risk": result.get("attrition_risk")},
                status_code=200,
                source="ml",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/predict-attrition/",
                request_payload={"feature_keys": sorted(list(payload.keys()))[:20] if isinstance(payload, dict) else []},
                response_payload={"detail": str(exc)},
                status_code=400,
                source="ml",
                error=str(exc),
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class RevenueForecastAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        started = start_timer()
        denied = _require_access(request.user, "forecast")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/forecast/",
                request_payload={"method": "GET"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        periods = int(request.query_params.get("periods", 4))
        history = request.query_params.getlist("history")
        result = forecast_revenue(periods=periods, history=[float(item) for item in history] if history else None)
        log_ai_usage(
            user=request.user,
            endpoint="/api/ai/forecast/",
            request_payload={"method": "GET", "periods": periods, "history_size": len(history)},
            response_payload={"method": result.get("method"), "source": result.get("source"), "forecast_size": len(result.get("forecast", []))},
            status_code=200,
            source=result.get("method", "forecast"),
            fallback_used=result.get("method") == "average_fallback",
            ip_address=get_client_ip(request),
            started_at=started,
        )
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request):
        started = start_timer()
        denied = _require_access(request.user, "forecast")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/forecast/",
                request_payload={"method": "POST"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        periods = int(request.data.get("periods", 4))
        history = request.data.get("history")
        result = forecast_revenue(periods=periods, history=history)
        history_size = len(history) if isinstance(history, list) else 0
        log_ai_usage(
            user=request.user,
            endpoint="/api/ai/forecast/",
            request_payload={"method": "POST", "periods": periods, "history_size": history_size},
            response_payload={"method": result.get("method"), "source": result.get("source"), "forecast_size": len(result.get("forecast", []))},
            status_code=200,
            source=result.get("method", "forecast"),
            fallback_used=result.get("method") == "average_fallback",
            ip_address=get_client_ip(request),
            started_at=started,
        )
        return Response(result, status=status.HTTP_200_OK)


class AnomalyDetectionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        started = start_timer()
        denied = _require_access(request.user, "anomaly")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/detect-anomaly/",
                request_payload={"method": "GET"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        project_id = request.query_params.get("project_id")
        history = request.query_params.getlist("values")
        result = detect_anomalies(
            values=[float(item) for item in history] if history else None,
            project_id=int(project_id) if project_id else None,
        )
        log_ai_usage(
            user=request.user,
            endpoint="/api/ai/detect-anomaly/",
            request_payload={"method": "GET", "project_id": project_id, "history_size": len(history)},
            response_payload={"method": result.get("method"), "count": result.get("count", 0)},
            status_code=200,
            source=result.get("method", "anomaly"),
            fallback_used=result.get("method") == "insufficient_data",
            ip_address=get_client_ip(request),
            started_at=started,
        )
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request):
        started = start_timer()
        denied = _require_access(request.user, "anomaly")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/detect-anomaly/",
                request_payload={"method": "POST"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        result = detect_anomalies(
            values=request.data.get("values"),
            project_id=request.data.get("project_id"),
        )
        values = request.data.get("values")
        log_ai_usage(
            user=request.user,
            endpoint="/api/ai/detect-anomaly/",
            request_payload={"method": "POST", "project_id": request.data.get("project_id"), "values_size": len(values) if isinstance(values, list) else 0},
            response_payload={"method": result.get("method"), "count": result.get("count", 0)},
            status_code=200,
            source=result.get("method", "anomaly"),
            fallback_used=result.get("method") == "insufficient_data",
            ip_address=get_client_ip(request),
            started_at=started,
        )
        return Response(result, status=status.HTTP_200_OK)


class ResourceRecommendationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        started = start_timer()
        denied = _require_access(request.user, "recommend")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/recommend-resource/",
                request_payload={"detail": "forbidden"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        result = recommend_resources(
            project_id=request.data.get("project_id"),
            required_departments=request.data.get("required_departments"),
            required_skills=request.data.get("required_skills"),
            hours_needed=request.data.get("hours_needed", 40),
        )
        log_ai_usage(
            user=request.user,
            endpoint="/api/ai/recommend-resource/",
            request_payload={
                "project_id": request.data.get("project_id"),
                "required_departments": request.data.get("required_departments"),
                "required_skills": request.data.get("required_skills"),
                "hours_needed": request.data.get("hours_needed", 40),
            },
            response_payload={"suggestion_count": len(result.get("suggestions", []))},
            status_code=200,
            source="rule-based",
            ip_address=get_client_ip(request),
            started_at=started,
        )
        return Response(result, status=status.HTTP_200_OK)


class RiskDetectionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        started = start_timer()
        denied = _require_access(request.user, "risk")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/risk-detect/",
                request_payload={"detail": "forbidden"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        project_id = request.query_params.get("project_id")
        if not project_id:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/risk-detect/",
                request_payload={},
                response_payload={"detail": "project_id is required."},
                status_code=400,
                source="validation",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response({"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = detect_project_risks(int(project_id))
            source = result.get("source", "rule-based")
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/risk-detect/",
                request_payload={"project_id": project_id},
                response_payload={"risk_count": len(result.get("risks", [])), "source": source},
                status_code=200,
                source=source,
                fallback_used=source == "rule-based",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/risk-detect/",
                request_payload={"project_id": project_id},
                response_payload={"detail": str(exc)},
                status_code=400,
                source="rule-based",
                error=str(exc),
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ProjectSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        started = start_timer()
        denied = _require_access(request.user, "report")
        if denied:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/report/",
                request_payload={"detail": "forbidden"},
                response_payload={"detail": "forbidden"},
                status_code=403,
                source="rbac",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return denied

        project_id = request.query_params.get("project_id")
        if not project_id:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/report/",
                request_payload={},
                response_payload={"detail": "project_id is required."},
                status_code=400,
                source="validation",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response({"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = summarize_project(int(project_id))
            source = result.get("source", "")
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/report/",
                request_payload={"project_id": project_id},
                response_payload={"source": source, "has_summary": bool(result.get("summary"))},
                status_code=200,
                source=source,
                fallback_used=source == "fallback",
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            log_ai_usage(
                user=request.user,
                endpoint="/api/ai/report/",
                request_payload={"project_id": project_id},
                response_payload={"detail": str(exc)},
                status_code=400,
                source="ollama",
                error=str(exc),
                ip_address=get_client_ip(request),
                started_at=started,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
