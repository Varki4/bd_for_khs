from django.core.cache import cache
from django.http import HttpResponseTooManyRequests
from functools import wraps
import time

def rate_limit(key_prefix, limit=100, period=3600):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            key = f"rate_limit:{key_prefix}:{request.META.get('REMOTE_ADDR')}"
            
            # Получаем текущее количество запросов
            requests = cache.get(key, 0)
            
            if requests >= limit:
                return HttpResponseTooManyRequests()
                
            cache.set(key, requests + 1, period)
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator