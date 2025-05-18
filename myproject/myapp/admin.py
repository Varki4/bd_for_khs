# myapp/admin.py
from django.contrib import admin
from .models import Cadet, Employee  # Импортируем модель Cadet вместо Book

# Зарегистрируйте модель Cadet в админке
admin.site.register(Cadet)
admin.site.register(Employee)
