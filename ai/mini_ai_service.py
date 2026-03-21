from __future__ import annotations

import json
import os
import pickle
from functools import lru_cache
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from budgeting.models import Expense, FinancialForecast
from projects.models import Project, Task
from resources.models import Employee, ResourceAllocation


BASE_DIR = Path(__file__).resolve().parent
ATTRITION_MODEL_PATH = BASE_DIR / "models" / "attrition_model.pkl"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text_items(items: Iterable[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _coerce_list(raw_value: Any) -> list[Any]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, tuple):
        return list(raw_value)
    if isinstance(raw_value, str):
        value = raw_value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [item.strip() for item in value.split(",") if item.strip()]
    return [raw_value]


def _load_json_list(raw_value: Any) -> list[float]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [_to_float(v) for v in raw_value]
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [_to_float(v) for v in parsed]
        except json.JSONDecodeError:
            pass
    return []


def _ollama_chat(system_prompt: str, user_prompt: str, context: dict[str, Any] | None = None) -> str | None:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_prompt
                + ("\n\nContext:\n" + json.dumps(context, ensure_ascii=False, indent=2) if context else ""),
            },
        ],
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if content:
            return content.strip()
    except Exception:
        return None
    return None


@lru_cache(maxsize=1)
def load_attrition_model():
    if not ATTRITION_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Attrition model not found at {ATTRITION_MODEL_PATH}. Run ai/train_attrition.py first."
        )
    with open(ATTRITION_MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict_attrition(features: dict[str, Any]) -> dict[str, Any]:
    required = [
        "Age",
        "JobLevel",
        "MonthlyIncome",
        "TotalWorkingYears",
        "YearsAtCompany",
        "JobSatisfaction",
        "OverTime",
    ]
    missing = [field for field in required if field not in features]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    row = {
        "Age": _to_float(features.get("Age")),
        "JobLevel": _to_float(features.get("JobLevel")),
        "MonthlyIncome": _to_float(features.get("MonthlyIncome")),
        "TotalWorkingYears": _to_float(features.get("TotalWorkingYears")),
        "YearsAtCompany": _to_float(features.get("YearsAtCompany")),
        "JobSatisfaction": _to_float(features.get("JobSatisfaction")),
        "OverTime": 1 if str(features.get("OverTime")).strip().lower() in {"1", "yes", "true", "y"} else 0,
    }

    model = load_attrition_model()
    frame = pd.DataFrame([row])
    probability = float(model.predict_proba(frame)[0][1])
    level = "HIGH" if probability >= 0.7 else "MEDIUM" if probability >= 0.4 else "LOW"

    return {
        "attrition_risk": round(probability, 4),
        "level": level,
        "features": row,
    }


def _get_revenue_history(values: list[float] | None = None) -> tuple[list[float], str]:
    if values:
        return values, "request"

    qs = FinancialForecast.objects.filter(forecast_type="revenue").order_by("period_year", "period_month")
    history = [float(item.amount) for item in qs]
    if history:
        return history, "db:financial_forecast"

    return [], "empty"


def forecast_revenue(periods: int = 4, history: list[float] | None = None) -> dict[str, Any]:
    series, source = _get_revenue_history([_to_float(value) for value in _coerce_list(history)] if history is not None else None)
    periods = max(1, min(int(periods or 4), 12))

    if len(series) < 2:
        avg = float(np.mean(series)) if series else 0.0
        forecast = [round(avg, 2) for _ in range(periods)]
        return {"forecast": forecast, "source": source, "method": "average_fallback"}

    ts = pd.Series(series, dtype="float64")
    try:
        model = ExponentialSmoothing(ts, trend="add", seasonal=None, initialization_method="estimated")
        fit = model.fit(optimized=True)
        raw = fit.forecast(periods)
        forecast = [round(float(value), 2) for value in raw]
        return {"forecast": forecast, "source": source, "method": "statsmodels_exponential_smoothing"}
    except Exception:
        avg = float(np.mean(series))
        forecast = [round(avg, 2) for _ in range(periods)]
        return {"forecast": forecast, "source": source, "method": "average_fallback"}


def detect_anomalies(values: list[float] | None = None, project_id: int | None = None) -> dict[str, Any]:
    if values is None and project_id is not None:
        values = list(
            Expense.objects.filter(project_id=project_id)
            .order_by("expense_date")
            .values_list("amount", flat=True)
        )

    series = [_to_float(v) for v in _coerce_list(values)]
    if len(series) < 5:
        return {
            "anomalies": [],
            "method": "insufficient_data",
            "message": "Need at least 5 values to detect anomalies reliably.",
        }

    frame = np.array(series, dtype=float).reshape(-1, 1)
    model = IsolationForest(contamination="auto", random_state=42)
    labels = model.fit_predict(frame)

    anomalies = []
    mean = float(np.mean(series))
    std = float(np.std(series)) or 1.0
    for index, (value, label) in enumerate(zip(series, labels)):
        if label == -1:
            z_score = abs((value - mean) / std)
            anomalies.append(
                {
                    "index": index,
                    "value": round(value, 2),
                    "z_score": round(z_score, 2),
                }
            )

    return {
        "anomalies": anomalies,
        "method": "isolation_forest",
        "count": len(anomalies),
    }


def recommend_resources(
    project_id: int | None = None,
    required_departments: list[str] | None = None,
    required_skills: list[str] | None = None,
    hours_needed: float = 40,
) -> dict[str, Any]:
    project = None
    if project_id:
        project = Project.objects.filter(id=project_id).first()

    departments = {item.lower() for item in _normalize_text_items(_coerce_list(required_departments))}
    skills = {item.lower() for item in _normalize_text_items(_coerce_list(required_skills))}

    active_employees = Employee.objects.filter(is_active=True).select_related("department")
    allocation_rows = (
        ResourceAllocation.objects.filter(Q(end_date__isnull=True) | Q(end_date__gte=timezone.localdate()))
        .values("employee_id")
        .annotate(total_allocated=Sum("allocation_percentage"))
    )
    allocation_map = {row["employee_id"]: float(row["total_allocated"] or 0) for row in allocation_rows}

    suggestions = []
    for employee in active_employees:
        current_load = allocation_map.get(employee.id, 0.0)
        availability = max(0.0, 100.0 - current_load) / 100.0
        department_name = (employee.department.name if employee.department else "").lower()
        position_name = (employee.position or "").lower()

        dept_score = 1.0 if departments and department_name in departments else 0.5 if departments else 0.3
        skill_score = 1.0 if skills and any(skill in position_name or skill in department_name for skill in skills) else 0.4 if skills else 0.3
        workload_score = availability
        rate = _to_float(employee.hourly_rate)
        cost_score = 1.0 / (1.0 + rate) if rate else 1.0

        score = round((dept_score * 0.35) + (skill_score * 0.35) + (workload_score * 0.2) + (cost_score * 0.1), 4)
        estimated_cost = round(rate * _to_float(hours_needed), 2)

        suggestions.append(
            {
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "department": employee.department.name if employee.department else None,
                "current_load": round(current_load, 2),
                "availability": round(availability, 2),
                "score": score,
                "estimated_cost": estimated_cost,
                "reason": "Matches department/skills and has enough availability.",
            }
        )

    suggestions.sort(key=lambda item: item["score"], reverse=True)
    return {
        "project_id": project_id,
        "project_name": project.name if project else None,
        "suggestions": suggestions[:5],
        "hours_needed": _to_float(hours_needed),
    }


def detect_project_risks(project_id: int) -> dict[str, Any]:
    project = Project.objects.filter(id=project_id).first()
    if not project:
        raise ValueError("Project not found")

    today = timezone.localdate()
    tasks = Task.objects.filter(project_id=project_id).select_related("assigned_to")
    overdue_tasks = tasks.filter(
        Q(due_date__lt=today) & ~Q(status="done")
    )
    risky_tasks = tasks.filter(
        Q(status__in=["todo", "in_progress", "review"]) &
        Q(due_date__isnull=False) &
        Q(due_date__lte=today + timedelta(days=7))
    )

    budget_risk = project.actual_budget > project.estimated_budget if project.estimated_budget else False
    progress = float(project.calculated_progress)
    deadline_risk = bool(project.end_date and project.end_date <= today + timedelta(days=7) and progress < 80)

    risks = []
    for task in overdue_tasks:
        risks.append(
            {
                "task_id": task.id,
                "task_name": task.name,
                "risk": "HIGH",
                "reason": "Overdue and not completed",
            }
        )
    for task in risky_tasks:
        risks.append(
            {
                "task_id": task.id,
                "task_name": task.name,
                "risk": "MEDIUM",
                "reason": "Deadline is close and progress is still low",
            }
        )

    if budget_risk:
        risks.append(
            {
                "task_id": None,
                "task_name": project.name,
                "risk": "HIGH",
                "reason": "Actual budget is above estimated budget",
            }
        )

    if deadline_risk:
        risks.append(
            {
                "task_id": None,
                "task_name": project.name,
                "risk": "MEDIUM",
                "reason": "Project deadline is near and progress is below target",
            }
        )

    return {
        "project_id": project.id,
        "project_name": project.name,
        "project_progress": round(progress, 2),
        "risks": risks,
        "summary": {
            "task_count": tasks.count(),
            "overdue_task_count": overdue_tasks.count(),
            "budget_risk": budget_risk,
            "deadline_risk": deadline_risk,
        },
    }


def summarize_project(project_id: int) -> dict[str, Any]:
    project = Project.objects.filter(id=project_id).first()
    if not project:
        raise ValueError("Project not found")

    tasks = Task.objects.filter(project_id=project_id)
    expenses = Expense.objects.filter(project_id=project_id)
    context = {
        "project": {
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "priority": project.priority,
            "progress": round(float(project.calculated_progress), 2),
            "estimated_budget": _to_float(project.estimated_budget),
            "actual_budget": _to_float(project.actual_budget),
        },
        "tasks": {
            "total": tasks.count(),
            "done": tasks.filter(status="done").count(),
            "overdue": tasks.filter(due_date__lt=timezone.localdate()).exclude(status="done").count(),
        },
        "finance": {
            "expense_total": _to_float(expenses.aggregate(total=Sum("amount"))["total"]),
        },
    }

    system_prompt = "You are a concise ERP project analyst. Return a short, practical project summary."
    user_prompt = (
        f"Summarize project {project.name} in 2-4 sentences. Mention progress, budget, risks, and one concrete next step."
    )
    ollama_text = _ollama_chat(system_prompt, user_prompt, context)
    if ollama_text:
        return {"summary": ollama_text, "context": context, "source": "ollama"}

    fallback = (
        f"Project {project.name} is at {context['project']['progress']}% progress. "
        f"It has {context['tasks']['done']}/{context['tasks']['total']} tasks done and "
        f"{context['tasks']['overdue']} overdue tasks. "
        f"Total expense is {context['finance']['expense_total']:.2f}."
    )
    return {"summary": fallback, "context": context, "source": "fallback"}


def answer_chat(message: str, role: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    system_prompt = (
        "You are a helpful ERP assistant. "
        "Answer briefly, practically, and in Vietnamese if the user asks in Vietnamese."
    )
    user_prompt = message.strip()
    content = _ollama_chat(system_prompt, user_prompt, context)
    if content:
        return {"answer": content, "source": "ollama", "context": context or {}}

    response_parts = [f"Bạn hỏi: {message.strip()}"]
    if context:
        response_parts.append(f"Dữ liệu hỗ trợ: {json.dumps(context, ensure_ascii=False)}")
    response_parts.append("Ollama chưa sẵn sàng nên đây là phản hồi fallback từ rule-based context.")
    return {"answer": " ".join(response_parts), "source": "fallback", "context": context or {}}


def build_chat_context(
    message: str,
    project_id: int | None = None,
    employee_id: int | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {"message": message}
    if project_id:
        project = Project.objects.filter(id=project_id).first()
        if project:
            context["project"] = {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "progress": round(float(project.calculated_progress), 2),
            }
    if employee_id:
        employee = Employee.objects.filter(id=employee_id).select_related("department").first()
        if employee:
            context["employee"] = {
                "id": employee.id,
                "name": employee.full_name,
                "department": employee.department.name if employee.department else None,
                "position": employee.position,
            }
    return context
