"""Compatibility AI service without cloud AI dependencies."""
from __future__ import annotations

import json
import re
import time
from decimal import Decimal
from typing import Any

from .mini_ai_service import (
    _ollama_chat,
    answer_chat,
    build_chat_context,
    detect_anomalies,
    detect_project_risks,
    forecast_revenue,
    predict_attrition,
    recommend_resources,
    summarize_project,
    get_last_ollama_error,
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
    FAST_TOTAL_BUDGET_SECONDS = 18.0

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
        if not context:
            return None

        system_prompt = (
            "Ban la tro ly AI cho ERP. "
            "Hay giai thich ngan gon vi sao top nhan su duoc de xuat cho du an. "
            "Tra ve toi da 5 y ngan gon, ro rang, tieng Viet."
        )
        user_prompt = (
            "Phan tich danh sach ranked_candidates trong context va giai thich theo "
            "muc tieu toi uu (optimization_goal), skill match, workload, va chi phi."
        )
        content = _ollama_chat(system_prompt, user_prompt, context)
        if not content:
            return None
        return {"reasoning": content}

    @staticmethod
    def _extract_json_payload(text: str) -> dict[str, Any] | None:
        if not text:
            return None
        raw = text.strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {"selected_candidates": data}
            return None
        except Exception:
            pass

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S | re.I)
        if fenced:
            try:
                data = json.loads(fenced.group(1))
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    return {"selected_candidates": data}
                return None
            except Exception:
                return None

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    return {"selected_candidates": data}
                return None
            except Exception:
                return None
        return None

    @staticmethod
    def _to_float_or_none(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        raw = str(value).strip()
        if not raw:
            return None
        cleaned = raw.replace(" ", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
        # Remove currency/text wrappers and keep number-ish chars
        cleaned = re.sub(r"[^\d,.\-]", "", cleaned)
        if not cleaned:
            return None
        try:
            # 12.000.000 -> 12000000 ; 12,5 -> 12.5 ; 12,000.50 -> 12000.50
            if "," in cleaned and "." in cleaned:
                if cleaned.rfind(",") > cleaned.rfind("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif cleaned.count(".") > 1:
                cleaned = cleaned.replace(".", "")
            elif cleaned.count(",") > 1:
                cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                frac = cleaned.split(",")[-1]
                if len(frac) <= 2:
                    cleaned = cleaned.replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            return float(cleaned)
        except Exception:
            return None

    @staticmethod
    def _pick_first(data: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)
        return None

    @staticmethod
    def _normalize_name(value: Any) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _normalize_ai_candidates(
        payload: dict[str, Any],
        max_recommendations: int,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        selected = payload.get("selected_candidates")
        if not isinstance(selected, list):
            selected = payload.get("recommendations")
        if not isinstance(selected, list):
            selected = payload.get("employees")
        if not isinstance(selected, list):
            selected = payload.get("items")
        if not isinstance(selected, list):
            return []

        pool_map: dict[int, dict[str, Any]] = {}
        name_map: dict[str, int] = {}
        for pool_item in (context or {}).get("candidate_pool", []):
            if not isinstance(pool_item, dict):
                continue
            try:
                pid = int(pool_item.get("employee_id"))
            except Exception:
                continue
            pool_map[pid] = pool_item
            normalized_name = AIService._normalize_name(pool_item.get("name"))
            if normalized_name:
                name_map[normalized_name] = pid

        normalized: list[dict[str, Any]] = []
        for item in selected:
            if isinstance(item, int):
                item = {"employee_id": item}
            elif isinstance(item, str):
                text = item.strip()
                if text.isdigit():
                    item = {"employee_id": int(text)}
                else:
                    continue
            if not isinstance(item, dict):
                continue
            try:
                employee_id_raw = AIService._pick_first(
                    item,
                    ["employee_id", "id", "employeeId", "emp_id", "staff_id"],
                )
                employee_id = int(employee_id_raw) if employee_id_raw is not None else 0
            except Exception:
                employee_id = 0
            if employee_id not in pool_map:
                possible_name = AIService._pick_first(item, ["name", "employee_name", "employeeName"])
                normalized_name = AIService._normalize_name(possible_name)
                employee_id = name_map.get(normalized_name, 0)
            if employee_id not in pool_map:
                continue

            allocation = AIService._to_float_or_none(
                AIService._pick_first(
                    item,
                    ["allocation_percentage", "allocation", "allocation_pct", "allocationPercent"],
                )
            )
            est_hours = AIService._to_float_or_none(
                AIService._pick_first(item, ["estimated_hours", "hours", "est_hours"])
            )
            est_cost = AIService._to_float_or_none(
                AIService._pick_first(item, ["estimated_cost", "cost", "est_cost", "total_cost"])
            )

            pool_row = pool_map.get(employee_id, {})
            full_cost = AIService._to_float_or_none(pool_row.get("estimated_cost_full_allocation")) or 0.0
            default_full_hours = AIService._to_float_or_none(pool_row.get("estimated_hours_full_allocation")) or 160.0

            if allocation is None and est_hours is not None:
                allocation = min(100.0, max(10.0, (est_hours / max(default_full_hours, 1.0)) * 100.0))
            if allocation is None and est_cost is not None and full_cost > 0:
                allocation = min(100.0, max(10.0, (est_cost / full_cost) * 100.0))
            if allocation is None:
                allocation = 100.0

            allocation = min(100.0, max(10.0, allocation))
            if est_hours is None:
                est_hours = default_full_hours * (allocation / 100.0)
            if est_cost is None:
                est_cost = full_cost * (allocation / 100.0) if full_cost > 0 else 0.0

            if est_hours <= 0:
                est_hours = default_full_hours * (allocation / 100.0)
            if est_cost < 0:
                est_cost = 0.0

            normalized.append(
                {
                    "employee_id": employee_id,
                    "allocation_percentage": allocation,
                    "estimated_hours": est_hours,
                    "estimated_cost": est_cost,
                    "reasoning": str(item.get("reasoning", "")).strip(),
                }
            )
            if len(normalized) >= max_recommendations:
                break
        return normalized

    @staticmethod
    def _recover_candidates_from_text(
        raw_text: str,
        context: dict[str, Any] | None = None,
        max_recommendations: int = 10,
    ) -> list[dict[str, Any]]:
        if not raw_text or not context:
            return []
        pool = context.get("candidate_pool", [])
        if not isinstance(pool, list):
            return []

        goal = str(context.get("optimization_goal", "balanced")).strip().lower()
        default_alloc = 100.0 if goal == "performance" else 60.0 if goal == "cost" else 80.0
        recovered: list[dict[str, Any]] = []
        lowered = raw_text.lower()

        for item in pool:
            if not isinstance(item, dict):
                continue
            try:
                employee_id = int(item.get("employee_id"))
            except Exception:
                continue
            name = str(item.get("name", "")).strip().lower()
            has_id = re.search(rf"\b{employee_id}\b", lowered) is not None
            has_name = bool(name) and name in lowered
            if not (has_id or has_name):
                continue

            full_hours = AIService._to_float_or_none(item.get("estimated_hours_full_allocation")) or 160.0
            full_cost = AIService._to_float_or_none(item.get("estimated_cost_full_allocation")) or 0.0
            hours = round(full_hours * (default_alloc / 100.0), 2)
            cost = round(full_cost * (default_alloc / 100.0), 2)
            recovered.append(
                {
                    "employee_id": employee_id,
                    "allocation_percentage": default_alloc,
                    "estimated_hours": hours,
                    "estimated_cost": max(0.0, cost),
                    "reasoning": "Recovered from LLM text output.",
                }
            )
            if len(recovered) >= max_recommendations:
                break
        return recovered

    @staticmethod
    def _compact_context_for_llm(context: dict[str, Any]) -> dict[str, Any]:
        max_recommendations = int(context.get("max_recommendations", 10))
        pool_limit = max(6, min(20, max_recommendations * 2))
        compact_pool = []
        for item in (context.get("candidate_pool") or [])[:pool_limit]:
            if not isinstance(item, dict):
                continue
            compact_pool.append(
                {
                    "employee_id": item.get("employee_id"),
                    "name": item.get("name"),
                    "department": item.get("department"),
                    "skill_match_score": item.get("skill_match_score"),
                    "performance_score": item.get("performance_score"),
                    "availability_score": item.get("availability_score"),
                    "cost_score": item.get("cost_score"),
                    "combined_score": item.get("combined_score"),
                    "estimated_cost_full_allocation": item.get("estimated_cost_full_allocation"),
                    "estimated_hours_full_allocation": item.get("estimated_hours_full_allocation"),
                }
            )

        return {
            "project_name": str(context.get("project_name") or "")[:120],
            "project_description": str(context.get("project_description") or "")[:220],
            "optimization_goal": context.get("optimization_goal"),
            "required_skills": list(context.get("required_skills") or [])[:12],
            "required_departments": list(context.get("required_departments") or [])[:8],
            "max_recommendations": max_recommendations,
            "hard_constraints": context.get("hard_constraints") or {},
            "candidate_pool": compact_pool,
        }

    @staticmethod
    def select_personnel_for_project(context):
        """
        LLM-first selector: model returns selected employee ids and allocation.
        Expected JSON:
        {
          "selected_candidates": [
            {"employee_id": 12, "allocation_percentage": 100, "reasoning": "..."}
          ],
          "overall_reasoning": "..."
        }
        """
        if not context:
            return None
        started_at = time.monotonic()
        compact_context = AIService._compact_context_for_llm(context)

        system_prompt = (
            "Ban la AI Resource Planner cho ERP. "
            "Chi tra ve JSON hop le, khong them text ngoai JSON."
        )
        user_prompt = (
            "Hay chon nhan su tu candidate_pool theo optimization_goal va required_skills. "
            "Bat buoc tra ve JSON dung schema sau:\n"
            "{\n"
            '  "selected_candidates": [\n'
            '    {\n'
            '      "employee_id": 1,\n'
            '      "allocation_percentage": 80,\n'
            '      "reasoning": "..."\n'
            '    }\n'
            "  ],\n"
            '  "overall_reasoning": "..."\n'
            "}\n"
            "Chi tra ve JSON, khong markdown."
        )
        content = _ollama_chat(system_prompt, user_prompt, compact_context, force_json=True, num_predict=120)
        if not content:
            return {
                "selected_candidates": [],
                "overall_reasoning": "",
                "error": get_last_ollama_error() or "Model did not return content.",
            }

        payload = AIService._extract_json_payload(content)
        max_recommendations = int(context.get("max_recommendations", 10))
        normalized = AIService._normalize_ai_candidates(payload or {}, max_recommendations, context=context)
        repaired = None

        # Pass 2: if pass 1 invalid/incomplete, ask model to convert to strict schema.
        if not normalized and (time.monotonic() - started_at) < AIService.FAST_TOTAL_BUDGET_SECONDS:
            repair_system_prompt = (
                "Ban la AI chuyen doi du lieu. "
                "Nhiem vu: chuyen output AI thanh JSON HOP LE theo schema bat buoc, "
                "chi tra ve JSON, khong markdown."
            )
            repair_user_prompt = (
                "Du lieu dau vao co the khong dung format. "
                "Hay dua tren candidate_pool va output_tho de tra ve JSON schema:\n"
                "{\n"
                '  "selected_candidates": [\n'
                '    {\n'
                '      "employee_id": 1,\n'
                '      "allocation_percentage": 50,\n'
                '      "estimated_hours": 80,\n'
                '      "estimated_cost": 12000000,\n'
                '      "reasoning": "..."\n'
                "    }\n"
                "  ],\n"
                '  "overall_reasoning": "..."\n'
                "}\n"
                "Bat buoc co du 4 truong so cho moi candidate."
            )
            repair_context = dict(compact_context)
            repair_context["output_tho"] = content
            repaired = _ollama_chat(repair_system_prompt, repair_user_prompt, repair_context, force_json=True, num_predict=120)
            repair_payload = AIService._extract_json_payload(repaired or "")
            normalized = AIService._normalize_ai_candidates(repair_payload or {}, max_recommendations, context=context)
            if normalized:
                payload = repair_payload or {}

        # Pass 3: ask AI to return id-only shortlist, then we infer numeric fields from candidate pool.
        if not normalized and (time.monotonic() - started_at) < AIService.FAST_TOTAL_BUDGET_SECONDS:
            compact_candidates = []
            for item in context.get("candidate_pool", [])[:20]:
                if not isinstance(item, dict):
                    continue
                compact_candidates.append(
                    {
                        "employee_id": item.get("employee_id"),
                        "name": item.get("name"),
                        "department": item.get("department"),
                        "skill_match_score": item.get("skill_match_score"),
                        "performance_score": item.get("performance_score"),
                        "availability_score": item.get("availability_score"),
                        "cost_score": item.get("cost_score"),
                        "combined_score": item.get("combined_score"),
                    }
                )

            pass3_system = (
                "Ban la AI Resource Planner. "
                "Chi tra ve JSON hop le, khong markdown, khong giai thich."
            )
            pass3_user = (
                "Chon nhan su phu hop nhat theo optimization_goal. "
                "Bat buoc tra ve JSON schema:\n"
                "{\n"
                '  "selected_candidates": [\n'
                '    {"employee_id": 1, "reasoning": "..."}\n'
                "  ],\n"
                '  "overall_reasoning": "..."\n'
                "}\n"
                "Chi duoc chon employee_id co trong candidate_pool."
            )
            pass3_context = {
                "project_name": compact_context.get("project_name"),
                "optimization_goal": compact_context.get("optimization_goal"),
                "required_skills": compact_context.get("required_skills"),
                "max_recommendations": compact_context.get("max_recommendations"),
                "candidate_pool": compact_candidates,
            }
            pass3_content = _ollama_chat(pass3_system, pass3_user, pass3_context, force_json=True, num_predict=96)
            pass3_payload = AIService._extract_json_payload(pass3_content or "")
            normalized = AIService._normalize_ai_candidates(pass3_payload or {}, max_recommendations, context=context)
            if normalized:
                payload = pass3_payload or payload

        if not normalized:
            normalized = AIService._recover_candidates_from_text(
                repaired or content,
                context=context,
                max_recommendations=max_recommendations,
            )
        if not normalized:
            return {
                "selected_candidates": [],
                "overall_reasoning": str(payload.get("overall_reasoning", "")).strip(),
                "error": "Model response format invalid after 3 passes.",
                "raw_content": content,
            }

        return {
            "selected_candidates": normalized,
            "overall_reasoning": str(payload.get("overall_reasoning", "")).strip(),
            "raw_content": content,
        }

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
