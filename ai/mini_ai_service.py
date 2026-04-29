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
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "20"))
LAST_OLLAMA_ERROR: str | None = None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _is_time_question(text: str) -> bool:
    t = (text or "").strip().lower()
    keywords = [
        "mấy giờ", "may gio", "bây giờ", "bay gio", "hiện tại", "hien tai",
        "giờ", "gio", "thời gian", "thoi gian", "hôm nay", "hom nay",
    ]
    return any(k in t for k in keywords)


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


def _ollama_chat(
    system_prompt: str,
    user_prompt: str,
    context: dict[str, Any] | None = None,
    force_json: bool = False,
    num_predict: int = 128,
) -> str | None:
    global LAST_OLLAMA_ERROR
    base_payload = {
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
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_predict": num_predict,
        },
    }

    def _call(payload: dict[str, Any]) -> str | None:
        global LAST_OLLAMA_ERROR
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            content = message.get("content")
            if content:
                LAST_OLLAMA_ERROR = None
                return content.strip()
            LAST_OLLAMA_ERROR = "Model returned empty content."
            return None
        except Exception as exc:
            LAST_OLLAMA_ERROR = str(exc)
            return None

    first_payload = dict(base_payload)
    if force_json:
        first_payload["format"] = "json"
    first = _call(first_payload)
    if first:
        return first

    # Retry once without strict JSON mode; upper layers already parse/repair outputs.
    if force_json:
        retry = _call(dict(base_payload))
        if retry:
            return retry

    return None


def get_last_ollama_error() -> str | None:
    return LAST_OLLAMA_ERROR


def _clean_vietnamese_report(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    # Remove common "thinking" leakage prefixes from local LLMs.
    blocked_markers = [
        "okay, let's",
        "first,",
        "i need to",
        "the user wants",
        "context provided",
        "let me structure",
        "nguồn:",
        "source:",
    ]
    lines = [ln.strip(" -\t") for ln in raw.splitlines() if ln.strip()]
    kept: list[str] = []
    for ln in lines:
        low = ln.lower()
        if any(m in low for m in blocked_markers):
            continue
        kept.append(ln)
    cleaned = " ".join(kept).strip()
    # Keep concise report size for UI/readability.
    if len(cleaned) > 1200:
        cleaned = cleaned[:1200].rstrip() + "..."
    return cleaned


def _looks_english_heavy(text: str) -> bool:
    t = (text or "").lower()
    markers = [
        "project",
        "summary",
        "risk level",
        "overall",
        "next step",
        "from the context",
        "we need to",
        "the project",
        "from the context",
        "first sentence",
        "second sentence",
        "we are given",
        "let's tackle",
    ]
    hits = sum(1 for m in markers if m in t)
    return hits >= 2


def _build_project_summary_vi(context: dict[str, Any]) -> str:
    project_name = context["project"]["name"]
    progress = context["project"]["progress"]
    total = context["tasks"]["total"]
    done = context["tasks"]["done"]
    overdue = context["tasks"]["overdue"]
    estimated_budget = context["project"]["estimated_budget"]
    actual_budget = context["project"]["actual_budget"]
    expense_total = context["finance"]["expense_total"]
    return (
        f"Dự án {project_name} hiện đạt khoảng {progress}% tiến độ, với {done}/{total} công việc đã hoàn thành. "
        f"Ngân sách kế hoạch là {estimated_budget:.0f}, ngân sách thực tế đang ghi nhận {actual_budget:.0f} và tổng chi phí hiện tại là {expense_total:.2f}. "
        f"Rủi ro chính tập trung ở tiến độ do có {overdue} công việc trễ hạn cần xử lý sớm. "
        "Đề xuất tiếp theo: ưu tiên nhóm task trễ hạn, rà soát lại deadline và cập nhật kế hoạch thực thi theo ngày."
    )


def _build_project_risk_report_vi(
    project_name: str,
    progress: float,
    task_count: int,
    overdue_task_count: int,
    budget_risk: bool,
    deadline_risk: bool,
) -> str:
    level = "THẤP"
    if overdue_task_count > 0 or deadline_risk:
        level = "TRUNG BÌNH"
    if overdue_task_count >= 2 or (deadline_risk and progress < 60):
        level = "CAO"
    sentence_1 = f"Dự án {project_name} hiện có mức rủi ro tổng quan {level}, tiến độ đạt {round(progress, 2)}%."
    sentence_2 = f"Hệ thống ghi nhận {overdue_task_count}/{task_count} công việc đang trễ hạn."
    sentence_3 = (
        "Rủi ro ngân sách đang xuất hiện do chi phí thực tế vượt kế hoạch."
        if budget_risk
        else "Rủi ro ngân sách hiện chưa đáng lo ngại."
    )
    sentence_4 = (
        "Rủi ro tiến độ cao vì mốc thời gian gần kề nhưng tiến độ chưa đạt mục tiêu."
        if deadline_risk
        else "Rủi ro tiến độ đang trong ngưỡng kiểm soát."
    )
    sentence_5 = "Hành động ưu tiên 1: xử lý ngay các task trễ hạn ảnh hưởng trực tiếp đến mốc bàn giao."
    sentence_6 = "Hành động ưu tiên 2: cập nhật lại kế hoạch nguồn lực và kiểm tra tiến độ hằng ngày trong tuần tới."
    return " ".join([sentence_1, sentence_2, sentence_3, sentence_4, sentence_5, sentence_6])


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
    try:
        if project_id in ("", "null", "None"):
            project_id = None
        elif project_id is not None:
            project_id = int(project_id)
    except (TypeError, ValueError):
        project_id = None

    project = None
    if project_id:
        project = Project.objects.filter(id=project_id).first()

    departments = {item.lower() for item in _normalize_text_items(_coerce_list(required_departments))}
    # Theo yeu cau tinh gon: bo loc ky nang, uu tien nang suat + dung han.
    skills = set()

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

        dept_score = 1.0 if departments and department_name in departments else 0.6 if departments else 0.4
        # Nang suat va dung han dua tren KPI + warning + delay score.
        kpi_current = float(employee.kpi_current or 100.0)
        warning_count = float(employee.warning_count or 0.0)
        delay_score = float(employee.total_delay_score or 0.0)
        productivity_score = min(1.0, max(0.0, kpi_current / 100.0))
        ontime_score = max(0.0, 1.0 - min(1.0, (warning_count * 0.12) + (delay_score / 200.0)))
        workload_score = availability
        rate = _to_float(employee.hourly_rate)
        cost_score = 1.0 / (1.0 + rate) if rate else 1.0

        score = round(
            (productivity_score * 0.4) +
            (ontime_score * 0.3) +
            (workload_score * 0.2) +
            (dept_score * 0.05) +
            (cost_score * 0.05),
            4,
        )
        estimated_cost = round(rate * _to_float(hours_needed), 2)

        suggestions.append(
            {
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "department": employee.department.name if employee.department else None,
                "current_load": round(current_load, 2),
                "availability": round(availability, 2),
                "kpi_current": round(kpi_current, 2),
                "warning_count": int(warning_count),
                "score": score,
                "estimated_cost": estimated_cost,
                "reason": "Nang suat tot, lich su dung han on, va con kha nang nhan viec.",
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

    base_result = {
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
        "source": "rule-based",
    }

    context = {
        "project_name": project.name,
        "project_status": project.status,
        "project_priority": project.priority,
        "project_progress": round(progress, 2),
        "summary": base_result["summary"],
        "top_risks": risks[:5],
    }
    system_prompt = (
        "Ban la chuyen gia quan tri rui ro du an ERP. "
        "Tra loi bang tieng Viet ro rang, ngan gon, thuc te."
    )
    user_prompt = (
        "Hay viet bao cao rui ro du an trong 4-6 cau: "
        "neu muc do tong quan, cac nguyen nhan chinh, va 2 hanh dong uu tien tiep theo."
    )
    ai_text = _ollama_chat(system_prompt, user_prompt, context, force_json=False, num_predict=220)
    if ai_text:
        cleaned = _clean_vietnamese_report(ai_text)
        if cleaned:
            base_result["risk"] = cleaned
            base_result["source"] = "ollama"
            return base_result

    # Deterministic direct report (no thinking/debug text).
    base_result["risk"] = _build_project_risk_report_vi(
        project_name=project.name,
        progress=progress,
        task_count=base_result["summary"]["task_count"],
        overdue_task_count=base_result["summary"]["overdue_task_count"],
        budget_risk=base_result["summary"]["budget_risk"],
        deadline_risk=base_result["summary"]["deadline_risk"],
    )
    if ai_text:
        base_result["source"] = "ollama"

    # Fallback when local LLM is unavailable.
    if not ai_text:
        base_result["source"] = "rule-based"
    return base_result


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

    system_prompt = (
        "Ban la chuyen gia phan tich du an ERP. "
        "Chi tra loi bang tieng Viet, ngan gon, ro rang, khong suy luan noi bo."
    )
    user_prompt = (
        f"Tom tat du an {project.name} trong 3-4 cau, gom: tien do, ngan sach, rui ro, "
        "va 1 hanh dong cu the tiep theo."
    )
    ollama_text = _ollama_chat(system_prompt, user_prompt, context)
    if ollama_text:
        cleaned = _clean_vietnamese_report(ollama_text)
        if cleaned and not _looks_english_heavy(cleaned):
            return {"summary": cleaned, "context": context, "source": "ollama"}

    fallback = _build_project_summary_vi(context)
    return {"summary": fallback, "context": context, "source": "fallback"}


def answer_chat(message: str, role: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    system_prompt = (
        "You are a helpful ERP assistant. "
        "Answer briefly, practically, and in Vietnamese if the user asks in Vietnamese."
    )
    user_prompt = message.strip()
    if _is_time_question(user_prompt):
        now = timezone.localtime()
        answer = now.strftime("Hiện tại là %H:%M:%S, ngày %d/%m/%Y.")
        return {"answer": answer, "source": "rule_based_time", "context": context or {}}

    content = _ollama_chat(system_prompt, user_prompt, context)
    if content:
        return {"answer": content, "source": "ollama", "context": context or {}}

    clean_message = message.strip()
    fallback = (
        "Hiện AI đang bận hoặc tạm thời chưa sẵn sàng. "
        f"Bạn vừa hỏi: \"{clean_message}\". "
        "Bạn có thể thử lại sau vài giây, hoặc bổ sung thông tin cụ thể "
        "(mã dự án, khoảng thời gian, phòng ban) để mình hỗ trợ tốt hơn."
    )
    return {"answer": fallback, "source": "fallback", "context": context or {}}


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


def _json_to_business_vietnamese(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("answer", "summary", "message", "result", "insight", "analysis"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        lines = []
        for k, v in data.items():
            if v in (None, "", [], {}):
                continue
            vv = _json_to_business_vietnamese(v) if isinstance(v, (dict, list)) else str(v)
            if vv:
                lines.append(f"{k}: {vv}")
        return ("Tong hop nhanh: " + "; ".join(lines[:6]) + ".") if lines else ""
    if isinstance(data, list):
        items = []
        for item in data[:8]:
            txt = _json_to_business_vietnamese(item) if isinstance(item, (dict, list)) else str(item)
            if txt:
                items.append(txt)
        return ("De xuat: " + "; ".join(items) + ".") if items else ""
    if isinstance(data, str):
        return data.strip()
    return str(data)


def _normalize_chat_answer_vi(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""

    candidate = raw
    if candidate.startswith("```"):
        candidate = candidate.strip("`").strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    try:
        parsed = json.loads(candidate)
        natural = _json_to_business_vietnamese(parsed)
        if natural:
            raw = natural
    except Exception:
        pass

    blocked_markers = [
        "okay, let's",
        "let's tackle",
        "the user wants",
        "first,",
        "i need to",
        "from the context",
        "we are given",
        "json:",
        "source:",
        "nguon:",
    ]
    lines = [ln.strip(" -\t") for ln in raw.splitlines() if ln.strip()]
    kept = []
    for ln in lines:
        low = ln.lower()
        if any(m in low for m in blocked_markers):
            continue
        kept.append(ln)
    cleaned = " ".join(kept).strip()
    if not cleaned or _looks_english_heavy(cleaned):
        return ""
    return cleaned


def answer_chat(message: str, role: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Override chat answer: Vietnamese business tone, strip thinking, normalize JSON to natural text."""
    system_prompt = (
        "Ban la tro ly AI cho he thong ERP doanh nghiep. "
        "Bat buoc tra loi bang tieng Viet tu nhien, phong cach chuyen nghiep doanh nghiep, "
        "ngan gon, ro rang, de hanh dong. "
        "Khong duoc tra ve suy luan noi bo, khong markdown, khong JSON."
    )
    user_prompt = message.strip()
    if _is_time_question(user_prompt):
        now = timezone.localtime()
        answer = now.strftime("Hien tai la %H:%M:%S, ngay %d/%m/%Y.")
        return {"answer": answer, "source": "rule_based_time", "context": context or {}}

    content = _ollama_chat(system_prompt, user_prompt, context)
    if content:
        normalized = _normalize_chat_answer_vi(content)
        if normalized:
            return {"answer": normalized, "source": "ollama", "context": context or {}}

    clean_message = message.strip()
    fallback = (
        "Hien tai AI chua tra ve noi dung phu hop de dung truc tiep. "
        f"Yeu cau cua ban: \"{clean_message}\". "
        "Vui long bo sung ma du an/phong ban/thoi gian de toi tra loi chinh xac theo ngu canh doanh nghiep."
    )
    return {"answer": fallback, "source": "fallback", "context": context or {}}
