# myapp/middleware.py
from django.contrib.auth import logout
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
import re
import logging

logger = logging.getLogger(__name__)

class SessionSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_token = request.session.get('session_token')
        if session_token and session_token != request.COOKIES.get('session_token'):
            logout(request)
        response = self.get_response(request)
        response.set_cookie('session_token', session_token)
        return response

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_rеsponse

    def __call__(self, request):
        # Проверка на SQL инъекции
        sql_patterns = r'(\bSELECT\b|\bUNION\b|\bDROP\b|\bDELETE\b|\bINSERT\b)'
        if request.method == 'POST':
            for key, value in request.POST.items():
                if re.search(sql_patterns, value, re.I):
                    return HttpResponseForbidden("Обнаружена попытка SQL-инъекции")

        response = self.get_response(request)
        
        # Безопасные заголовки
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        return response

class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Проверяем валидность сессии
            if not request.session.session_key:
                request.session.create()
                logger.warning(f"Session created for user {request.user.username}")
            
            # Обновляем сессию при каждом запросе
            request.session.modified = True
        
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated:
            # Проверяем, что сессия активна
            if not request.session.session_key:
                logout(request)
                logger.warning("User logged out due to missing session")
                return HttpResponseRedirect(reverse('login'))
        return None
