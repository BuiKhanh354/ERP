"""AI Chat views for PRM AI."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Q
import json
import uuid

from ai.services import AIService
from core.models import AIChatHistory


class AIChatView(LoginRequiredMixin, TemplateView):
    """Chat interface with PRM AI."""
    template_name = 'pages/ai_chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Chat với PRM AI'
        
        # Get or create session ID
        session_id = self.request.GET.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
        context['session_id'] = session_id
        
        # Load chat history for this session
        chat_history = AIChatHistory.objects.filter(
            user=self.request.user,
            session_id=session_id
        ).order_by('created_at')[:50]
        
        context['chat_history'] = [
            {
                'message': chat.message,
                'response': chat.response,
                'created_at': chat.created_at
            }
            for chat in chat_history
        ]
        
        return context


@method_decorator(csrf_exempt, name='dispatch')
class AIChatAPIView(LoginRequiredMixin, View):
    """API endpoint for AI chat."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            session_id = data.get('session_id', str(uuid.uuid4()))
            
            if not message:
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Use AI service to generate response
            model = AIService._get_gemini_client()
            
            # Get recent chat history for context
            recent_history = AIChatHistory.objects.filter(
                user=request.user,
                session_id=session_id
            ).order_by('-created_at')[:5]
            
            # Build context from history
            context_messages = []
            for chat in reversed(recent_history):
                context_messages.append(f"User: {chat.message}")
                context_messages.append(f"Assistant: {chat.response}")
            
            # Build context-aware prompt
            context_prompt = f"""Bạn là PRM AI, trợ lý ERP cho doanh nghiệp dịch vụ. Nhiệm vụ chính: sinh báo cáo và trả lời ngắn gọn, đúng khuôn khổ web (text thuần, không markdown).
Bạn có thể:
- Phân tích tổng quan hoặc dự án cụ thể (tiến độ, ngân sách, rủi ro, hành động).
- Phân tích ngân sách, mua sắm, nhân sự, hiệu suất, KPI.
- Đề xuất hành động ngắn gọn, dễ thực thi.

HƯỚNG DẪN TRẢ LỜI:
- Ngôn ngữ: tiếng Việt, chuyên nghiệp, súc tích.
- Độ dài: tối đa 2-3 đoạn ngắn, hoặc danh sách gạch đầu dòng (-).
- Không dùng markdown (*, **, #). Dùng '-' cho bullet; xuống dòng để tách ý.
- Nếu câu hỏi yêu cầu báo cáo tổng quan: tóm tắt 3-5 ý chính (tiến độ, ngân sách, rủi ro, nhân sự, hành động).
- Nếu báo cáo dự án cụ thể: nêu tiến độ, ngân sách/chi tiêu, rủi ro, phụ thuộc, 3-4 hành động khuyến nghị.
- Nếu thiếu thông tin (tên/mã dự án, phạm vi, mốc thời gian), hãy hỏi lại ngắn gọn để lấy đủ dữ liệu rồi mới trả lời.

"""
            
            if context_messages:
                context_prompt += "\n\nLịch sử trò chuyện trước đó:\n" + "\n".join(context_messages) + "\n"
            
            context_prompt += f"\nCâu hỏi của người dùng: {message}"
            
            response = model.generate_content(context_prompt)
            response_text = response.text
            
            # Clean up markdown formatting from response
            import re
            # Remove markdown bold/italic markers
            response_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', response_text)  # Remove **bold**
            response_text = re.sub(r'\*([^*]+)\*', r'\1', response_text)  # Remove *italic*
            response_text = re.sub(r'#+\s*', '', response_text)  # Remove markdown headers
            response_text = re.sub(r'```[\s\S]*?```', '', response_text)  # Remove code blocks
            response_text = re.sub(r'`([^`]+)`', r'\1', response_text)  # Remove inline code
            # Replace markdown list markers with simple dashes
            response_text = re.sub(r'^\s*[-*+]\s+', '- ', response_text, flags=re.MULTILINE)
            # Clean up extra whitespace
            response_text = re.sub(r'\n{3,}', '\n\n', response_text)
            response_text = response_text.strip()
            
            # Save chat history
            AIChatHistory.objects.create(
                user=request.user,
                message=message,
                response=response_text,
                session_id=session_id,
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'response': response_text,
                'message': message,
                'session_id': session_id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class AIChatHistoryView(LoginRequiredMixin, ListView):
    """View for AI chat history."""
    model = AIChatHistory
    template_name = 'pages/ai_chat_history.html'
    context_object_name = 'chat_sessions'
    paginate_by = 20

    def get_queryset(self):
        # Get unique sessions for the user
        sessions = AIChatHistory.objects.filter(
            user=self.request.user
        ).values('session_id').distinct()
        
        # Get latest message for each session
        session_list = []
        for session in sessions:
            session_id = session['session_id']
            latest_chat = AIChatHistory.objects.filter(
                user=self.request.user,
                session_id=session_id
            ).order_by('-created_at').first()
            
            if latest_chat:
                session_list.append({
                    'session_id': session_id,
                    'last_message': latest_chat.message[:100],
                    'last_response': latest_chat.response[:100],
                    'last_updated': latest_chat.created_at,
                    'message_count': AIChatHistory.objects.filter(
                        user=self.request.user,
                        session_id=session_id
                    ).count()
                })
        
        # Sort by last updated
        session_list.sort(key=lambda x: x['last_updated'], reverse=True)
        return session_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Lịch sử Chat AI'
        return context


@method_decorator(csrf_exempt, name='dispatch')
class AIChatDeleteView(LoginRequiredMixin, View):
    """API endpoint to delete a chat session."""
    
    def delete(self, request):
        try:
            session_id = request.GET.get('session_id')
            if not session_id:
                return JsonResponse({'success': False, 'error': 'Session ID is required'}, status=400)
            
            # Delete all messages in this session for the current user
            deleted_count = AIChatHistory.objects.filter(
                user=request.user,
                session_id=session_id
            ).delete()[0]
            
            if deleted_count > 0:
                return JsonResponse({
                    'success': True,
                    'message': f'Đã xóa {deleted_count} tin nhắn trong phiên chat này.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Không tìm thấy phiên chat để xóa.'
                }, status=404)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
