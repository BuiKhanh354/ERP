"""AI Chat views for PRM AI."""
from __future__ import annotations

import json
import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView, TemplateView

from ai.mini_ai_service import answer_chat, build_chat_context
from core.models import AIChatHistory


class AIChatView(LoginRequiredMixin, TemplateView):
    """Chat interface with PRM AI."""
    template_name = "pages/ai_chat.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Chat với PRM AI"

        session_id = self.request.GET.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
        context["session_id"] = session_id

        chat_history = AIChatHistory.objects.filter(
            user=self.request.user,
            session_id=session_id,
        ).order_by("created_at")[:50]

        context["chat_history"] = [
            {
                "message": chat.message,
                "response": chat.response,
                "created_at": chat.created_at,
            }
            for chat in chat_history
        ]
        return context


@method_decorator(csrf_exempt, name="dispatch")
class AIChatAPIView(LoginRequiredMixin, View):
    """Compatibility AI chat API used by web chat UI."""

    def post(self, request):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"success": False, "error": "Payload không hợp lệ."}, status=400)

        message = str(payload.get("message", "")).strip()
        session_id = str(payload.get("session_id", "")).strip() or str(uuid.uuid4())
        if not message:
            return JsonResponse({"success": False, "error": "message is required."}, status=400)

        try:
            context = build_chat_context(message=message)
            result = answer_chat(
                message=message,
                role=getattr(getattr(request.user, "profile", None), "role", None),
                context=context,
            )

            response_text = (
                result.get("answer")
                or result.get("summary")
                or result.get("message")
                or "Xin lỗi, tôi chưa có phản hồi phù hợp."
            )

            AIChatHistory.objects.create(
                user=request.user,
                message=message,
                response=response_text,
                session_id=session_id,
            )

            return JsonResponse(
                {
                    "success": True,
                    "response": response_text,
                    "session_id": session_id,
                    "source": result.get("source", "fallback"),
                }
            )
        except Exception as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=500)


class AIChatHistoryView(LoginRequiredMixin, ListView):
    """View for AI chat history."""
    model = AIChatHistory
    template_name = "pages/ai_chat_history.html"
    context_object_name = "chat_sessions"
    paginate_by = 20

    def get_queryset(self):
        sessions = AIChatHistory.objects.filter(user=self.request.user).values("session_id").distinct()

        session_list = []
        for session in sessions:
            session_id = session["session_id"]
            latest_chat = AIChatHistory.objects.filter(
                user=self.request.user,
                session_id=session_id,
            ).order_by("-created_at").first()

            if latest_chat:
                session_list.append(
                    {
                        "session_id": session_id,
                        "last_message": latest_chat.message[:100],
                        "last_response": latest_chat.response[:100],
                        "last_updated": latest_chat.created_at,
                        "message_count": AIChatHistory.objects.filter(
                            user=self.request.user,
                            session_id=session_id,
                        ).count(),
                    }
                )

        session_list.sort(key=lambda x: x["last_updated"], reverse=True)
        return session_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Lịch sử Chat AI"
        return context


@method_decorator(csrf_exempt, name="dispatch")
class AIChatDeleteView(LoginRequiredMixin, View):
    """API endpoint to delete a chat session."""

    def delete(self, request):
        session_id = request.GET.get("session_id")
        if not session_id:
            return JsonResponse({"success": False, "error": "Session ID is required"}, status=400)

        deleted_count = AIChatHistory.objects.filter(
            user=request.user,
            session_id=session_id,
        ).delete()[0]

        if deleted_count > 0:
            return JsonResponse({
                "success": True,
                "message": f"Đã xóa {deleted_count} tin nhắn trong phiên chat này.",
            })

        return JsonResponse({
            "success": False,
            "error": "Không tìm thấy phiên chat để xóa.",
        }, status=404)
