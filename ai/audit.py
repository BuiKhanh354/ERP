import json
from time import perf_counter

from core.models import AuditLog


def start_timer() -> float:
    return perf_counter()


def log_ai_usage(
    *,
    user,
    endpoint: str,
    request_payload=None,
    response_payload=None,
    status_code: int = 200,
    source: str = "",
    fallback_used: bool = False,
    error: str = "",
    ip_address: str | None = None,
    started_at: float | None = None,
) -> None:
    """Write AI usage telemetry into system audit log (no schema changes required)."""
    try:
        latency_ms = None
        if started_at is not None:
            latency_ms = round((perf_counter() - started_at) * 1000, 2)

        payload = {
            "endpoint": endpoint,
            "status_code": status_code,
            "source": source or "",
            "fallback_used": bool(fallback_used),
            "latency_ms": latency_ms,
            "error": error or "",
            "request": request_payload or {},
            "response": response_payload or {},
        }

        AuditLog.objects.create(
            user=user,
            action_type="UPDATE",
            table_name="ai_usage",
            record_id=str(endpoint),
            new_data=json.dumps(payload, ensure_ascii=False, default=str),
            ip_address=ip_address or "",
        )
    except Exception:
        # Never break business/API flow because of telemetry logging.
        return
