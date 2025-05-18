FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Устанавливаем необходимые системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем необходимые директории
RUN mkdir -p /app/media/cadet_documents

# Копируем только requirements.txt сначала
COPY requirements.txt .

# Устанавливаем зависимости с обновленными версиями
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf ~/.cache/pip

# Копируем остальные файлы проекта
COPY . .

# Устанавливаем правильные права на директории
RUN chmod -R 755 /app/media

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"] 