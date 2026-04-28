from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import OperationalError

from ai.mini_ai_service import (
    answer_chat,
    detect_anomalies,
    detect_project_risks,
    forecast_revenue,
    predict_attrition,
    recommend_resources,
    summarize_project,
)
from projects.models import Project, Task


class Command(BaseCommand):
    help = "Smoke test AI features and print PASS/FAIL summary for quick demo validation."

    def _ok(self, name: str, detail: str = ""):
        msg = f"[PASS] {name}"
        if detail:
            msg += f" -> {detail}"
        self.stdout.write(self.style.SUCCESS(msg))

    def _fail(self, name: str, exc: Exception):
        self.stdout.write(self.style.ERROR(f"[FAIL] {name} -> {exc}"))

    def _skip(self, name: str, reason: str):
        self.stdout.write(self.style.WARNING(f"[SKIP] {name} -> {reason}"))

    def handle(self, *args, **options):
        passed = 0
        failed = 0
        skipped = 0

        # 1) Chat AI
        try:
            chat = answer_chat("Tóm tắt trạng thái dự án hôm nay")
            self._ok("AI Chat", f"source={chat.get('source', 'unknown')}")
            passed += 1
        except Exception as exc:
            self._fail("AI Chat", exc)
            failed += 1

        # 2) Attrition prediction (ML)
        try:
            result = predict_attrition(
                {
                    "Age": 30,
                    "JobLevel": 2,
                    "MonthlyIncome": 12000,
                    "TotalWorkingYears": 7,
                    "YearsAtCompany": 3,
                    "JobSatisfaction": 3,
                    "OverTime": "No",
                }
            )
            self._ok("Attrition ML", f"level={result.get('level')}, risk={result.get('attrition_risk')}")
            passed += 1
        except Exception as exc:
            self._fail("Attrition ML", exc)
            failed += 1

        # 3) Revenue forecast
        try:
            result = forecast_revenue(periods=3, history=[1000, 1200, 1350, 1500, 1700, 1850])
            self._ok("Revenue Forecast", f"method={result.get('method')}, n={len(result.get('forecast', []))}")
            passed += 1
        except Exception as exc:
            self._fail("Revenue Forecast", exc)
            failed += 1

        # 4) Anomaly detection
        try:
            result = detect_anomalies(values=[100, 110, 95, 105, 500, 98, 102, 99])
            self._ok("Anomaly Detection", f"method={result.get('method')}, anomalies={result.get('count', 0)}")
            passed += 1
        except Exception as exc:
            self._fail("Anomaly Detection", exc)
            failed += 1

        # 5) Resource recommendation (rule-based)
        try:
            rec = recommend_resources(project_id=None, required_departments=["IT"], required_skills=["python"], hours_needed=24)
            self._ok("Resource Recommendation", f"suggestions={len(rec.get('suggestions', []))}")
            passed += 1
        except OperationalError as exc:
            self._skip("Resource Recommendation", f"DB unavailable: {exc}")
            skipped += 1
        except Exception as exc:
            self._fail("Resource Recommendation", exc)
            failed += 1

        # 6) Project risk + summary (requires at least 1 project)
        project_db_unavailable = False
        try:
            project = Project.objects.order_by("id").first()
        except OperationalError as exc:
            self._skip("Project Risk Detection", f"DB unavailable: {exc}")
            self._skip("Project Summary", f"DB unavailable: {exc}")
            skipped += 2
            project_db_unavailable = True
            project = None

        if project:
            try:
                risk = detect_project_risks(project.id)
                self._ok("Project Risk Detection", f"project_id={project.id}, risks={len(risk.get('risks', []))}")
                passed += 1
            except Exception as exc:
                self._fail("Project Risk Detection", exc)
                failed += 1

            try:
                summary = summarize_project(project.id)
                self._ok("Project Summary", f"source={summary.get('source', 'unknown')}")
                passed += 1
            except Exception as exc:
                self._fail("Project Summary", exc)
                failed += 1
        else:
            if not project_db_unavailable:
                self._skip("Project Risk Detection", "No project in DB")
                self._skip("Project Summary", "No project in DB")
                skipped += 2

        # 7) Task risk ML/fallback readiness (requires at least 1 task)
        task_db_unavailable = False
        try:
            task = Task.objects.select_related("assigned_to").order_by("id").first()
        except OperationalError as exc:
            self._skip("Task Risk Assessment", f"DB unavailable: {exc}")
            skipped += 1
            task_db_unavailable = True
            task = None

        if task:
            from projects.task_views import build_task_risk_assessment_ml_or_fallback

            try:
                assessment = build_task_risk_assessment_ml_or_fallback(task)
                self._ok(
                    "Task Risk Assessment",
                    f"engine={assessment.get('engine')}, level={assessment.get('risk_level')}, score={assessment.get('risk_score')}",
                )
                passed += 1
            except Exception as exc:
                self._fail("Task Risk Assessment", exc)
                failed += 1
        else:
            if not task_db_unavailable:
                self._skip("Task Risk Assessment", "No task in DB")
                skipped += 1

        self.stdout.write("")
        self.stdout.write("========== AI SMOKE TEST SUMMARY ==========")
        self.stdout.write(self.style.SUCCESS(f"PASSED: {passed}"))
        self.stdout.write(self.style.ERROR(f"FAILED: {failed}"))
        self.stdout.write(self.style.WARNING(f"SKIPPED: {skipped}"))

        if failed > 0:
            raise SystemExit(1)
