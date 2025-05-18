# myapp/templatetags/custom_filters.py
from django import template
import base64
import logging
from django.template.defaultfilters import date as date_filter
from base64 import b64encode as b64encode_original

logger = logging.getLogger(__name__)

register = template.Library()

@register.filter(name='b64encode', is_safe=True)
def b64encode(value):
    """
    Фильтр для кодирования файлов в base64 или получения URL
    """
    try:
        if hasattr(value, 'url'):
            # Для FileField, возвращаем URL
            return value.url
        elif hasattr(value, 'read'):
            # Для FileField/FieldFile
            content = value.read()
            if isinstance(content, str):
                content = content.encode('utf-8')
            return base64.b64encode(content).decode('utf-8')
        elif isinstance(value, memoryview):
            return base64.b64encode(value.tobytes()).decode('utf-8')
        elif isinstance(value, bytes):
            return base64.b64encode(value).decode('utf-8')
        elif hasattr(value, 'file'):
            # Для Django FileField
            value.file.seek(0)
            content = value.file.read()
            if isinstance(content, str):
                content = content.encode('utf-8')
            return base64.b64encode(content).decode('utf-8')
        else:
            return ''
    except Exception as e:
        logger.error(f"Error encoding file: {e}")
        return ''
    finally:
        # Сбрасываем указатель файла
        if hasattr(value, 'file'):
            try:
                value.file.seek(0)
            except Exception:
                pass

@register.filter
def custom_date(value):
    """
    Форматирует дату в формате "d E Y г." без апострофа
    """
    if not value:
        return ''
    try:
        # Используем стандартный фильтр date, но убираем апостроф
        formatted_date = date_filter(value, "d E Y'г.")
        return formatted_date.replace("'", "")
    except Exception as e:
        print(f"Error in custom_date filter: {e}")
        return ''