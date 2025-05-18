from .models import SupportInfo

def support_info(request):
    """
    Добавляет информацию о поддержке в контекст всех шаблонов
    """
    info = SupportInfo.objects.first()
    return {
        'support_info': info
    } 