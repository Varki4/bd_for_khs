# models.py
from django.db import models
from django.core.validators import MinLengthValidator
from django.utils.html import strip_tags
import base64
from storages.backends.s3boto3 import S3Boto3Storage
import logging
from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
import re
import os
import urllib.parse
import uuid
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class YandexS3Storage(S3Boto3Storage):
    """
    Класс для работы с Yandex Object Storage
    """
    def __init__(self, **kwargs):
        # Получаем учетные данные из настроек
        self.access_key = settings.AWS_ACCESS_KEY_ID
        self.secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.endpoint_url = settings.AWS_S3_ENDPOINT_URL
        
        # Создаем собственную сессию boto3 с правильными настройками
        session = boto3.session.Session()
        self.s3 = session.client(
            service_name='s3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            endpoint_url=self.endpoint_url,
            region_name='ru-central1',
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            )
        )
        
        # Проверяем наличие бакета
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully connected to bucket: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"Bucket {self.bucket_name} does not exist")
            elif error_code == '403':
                logger.error(f"Access denied to bucket {self.bucket_name}")
            else:
                logger.error(f"Error checking bucket {self.bucket_name}: {e}")
                
        # Инициализируем базовый класс со специальными настройками для Яндекс
        super().__init__(
            access_key=self.access_key,
            secret_key=self.secret_key,
            bucket_name=self.bucket_name,
            endpoint_url=self.endpoint_url,
            region_name='ru-central1',
            default_acl='private',
            custom_domain=None,
            addressing_style='path',
            file_overwrite=True,
            signature_version='s3v4',
            querystring_auth=False
        )

    def _save(self, name, content):
        """
        Метод для сохранения файла в Яндекс S3
        """
        try:
            # Генерируем уникальное имя файла с сохранением расширения
            original_ext = os.path.splitext(name)[1]
            unique_name = f"{uuid.uuid4().hex}{original_ext}"
            
            # Получаем путь без имени файла
            path = os.path.dirname(name)
            if path:
                # Объединяем путь с новым именем файла
                name = f"{path}/{unique_name}"
            else:
                name = unique_name
                
            # Нормализуем имя файла
            cleaned_name = self._clean_name(name)
            name = self._normalize_name(cleaned_name)
            
            logger.info(f"Saving file to Yandex S3: {name}")
            
            # Читаем содержимое файла
            if hasattr(content, 'read'):
                if hasattr(content, 'seek'):
                    content.seek(0)
                file_content = content.read()
                if hasattr(content, 'seek'):
                    content.seek(0)
            else:
                file_content = content

            # Загружаем файл напрямую через boto3 клиент
            try:
                self.s3.put_object(
                    Bucket=self.bucket_name,
                    Key=name,
                    Body=file_content,
                    ACL='private'
                )
                logger.info(f"Successfully saved file to Yandex S3: {name}")
                return name
            except Exception as e:
                logger.error(f"Error saving file to Yandex S3 {name}: {str(e)}")
                raise
                    
        except Exception as e:
            logger.error(f"Error in _save method: {str(e)}")
            raise

    def _open(self, name, mode='rb'):
        """
        Метод для открытия файла из Яндекс S3
        """
        try:
            name = self._normalize_name(self._clean_name(name))
            logger.info(f"Opening file from Yandex S3: {name}")
            
            # Используем стандартный метод открытия файла из S3Boto3Storage
            return super()._open(name, mode)
            
        except Exception as e:
            logger.error(f"Error opening file from Yandex S3: {name}, error: {str(e)}")
            raise

    def delete(self, name):
        """
        Метод для удаления файла из Яндекс S3
        """
        try:
            if not name:
                return
                
            name = self._normalize_name(self._clean_name(name))
            logger.info(f"Deleting file from Yandex S3: {name}")
            
            try:
                self.s3.delete_object(
                    Bucket=self.bucket_name,
                    Key=name
                )
                logger.info(f"Successfully deleted file from Yandex S3: {name}")
            except Exception as e:
                logger.error(f"Error deleting file from Yandex S3: {name}, error: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in delete method: {str(e)}")

    def exists(self, name):
        """
        Проверяет существование файла в Яндекс S3
        """
        try:
            name = self._normalize_name(self._clean_name(name))
            
            try:
                self.s3.head_object(
                    Bucket=self.bucket_name,
                    Key=name
                )
                return True
            except ClientError:
                return False
                
        except Exception as e:
            logger.error(f"Error checking if file exists in Yandex S3: {name}, error: {str(e)}")
            return False

    def url(self, name):
        """
        Формирует URL для доступа к файлу
        """
        try:
            if not name:
                return None
                
            name = self._normalize_name(self._clean_name(name))
            url = f"{self.endpoint_url}/{self.bucket_name}/{name}"
            return url
            
        except Exception as e:
            logger.error(f"Error generating URL for {name}: {str(e)}")
            return None

    def _clean_name(self, name):
        """
        Очищаем имя файла от недопустимых символов
        """
        return os.path.normpath(name).replace('\\', '/')

    def _normalize_name(self, name):
        """
        Нормализуем имя файла для Yandex Object Storage
        """
        return name.lstrip('/')

class CadetDocument(models.Model):
    cadet = models.ForeignKey('Cadet', on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=20)  # passport, registration, snils, medical
    file = models.FileField(upload_to='cadet_documents/%Y/%m/%d/', storage=YandexS3Storage())
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.doc_type} for {self.cadet.full_name}"

    def save(self, *args, **kwargs):
        if not self.filename and hasattr(self.file, 'name'):
            self.filename = self.file.name
        
        # Проверяем существование документа того же типа
        try:
            existing_doc = CadetDocument.objects.get(
                cadet=self.cadet,
                doc_type=self.doc_type
            )
            if existing_doc != self:
                # Удаляем старый файл из Object Storage
                try:
                    existing_doc.file.delete(save=False)
                except Exception as e:
                    logger.error(f"Error deleting old file from storage: {e}")
                # Удаляем старую запись
                existing_doc.delete()
        except CadetDocument.DoesNotExist:
            pass

        # Обновляем метаданные
        if not self.metadata:
            self.metadata = {}
            
        self.metadata.update({
            'cadet_id': str(self.cadet.id),
            'cadet_name': self.cadet.full_name,
            'doc_type': self.doc_type,
            'upload_date': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'filename': self.filename,
            'storage_path': f"cadet_documents/{self.uploaded_at.strftime('%Y/%m/%d')}/{self.filename}" if self.uploaded_at else None,
            'file_size': self.file.size if hasattr(self.file, 'size') else None,
            'content_type': self.file.content_type if hasattr(self.file, 'content_type') else None
        })
        
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Удаляем файл из Object Storage перед удалением записи
        if self.file:
            try:
                self.file.delete(save=False)
            except Exception as e:
                logger.error(f"Error deleting file from storage: {e}")
        super().delete(*args, **kwargs)

    @property
    def file_url(self):
        """
        Получаем публичный URL файла
        """
        if self.file:
            try:
                return self.file.url
            except Exception as e:
                logger.error(f"Error getting file URL: {e}")
                return None
        return None

    @property
    def file_size_formatted(self):
        """
        Возвращаем размер файла в человекочитаемом формате
        """
        try:
            size = self.metadata.get('file_size') or (self.file.size if hasattr(self.file, 'size') else 0)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except Exception as e:
            logger.error(f"Error formatting file size: {e}")
            return "Unknown size"

class Cadet(models.Model):
    full_name = models.CharField(max_length=255)
    birth_date = models.DateField()
    grade = models.CharField(max_length=4, verbose_name='Класс', help_text='Например: 9А, 11Б', null=True, blank=True)
    personal_info = models.TextField(null=True, blank=True)  
    achievements = models.TextField(null=True, blank=True)
    reprimands = models.TextField(null=True, blank=True)

    def clean_grade(self):
        if not self.grade:
            return self.grade
        
        # Удаляем все пробелы
        grade = ''.join(self.grade.split())
        
        # Находим числовую часть и буквенную часть
        number_part = ''
        letter_part = ''
        
        for char in grade:
            if char.isdigit():
                number_part += char
            elif char.isalpha():
                # Проверяем, что это русская буква
                if 'А' <= char.upper() <= 'Я':
                    letter_part += char.upper()
        
        if not number_part:
            raise ValidationError('Класс должен содержать цифру')
        
        if not letter_part:
            raise ValidationError('Класс должен содержать букву')
        
        return f"{number_part}{letter_part}"

    def save(self, *args, **kwargs):
        if self.grade:
            try:
                self.grade = self.clean_grade()
            except ValidationError as e:
                raise ValidationError(f'Ошибка в формате класса: {str(e)}')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.grade or 'Класс не указан'})"

    def get_documents(self):
        documents = {}
        for doc in self.documents.all():
            try:
                # Получаем URL файла вместо попытки кодирования
                file_url = doc.file.url if doc.file else None
                documents[doc.doc_type] = {
                    'name': doc.filename,
                    'url': file_url,
                    'type': doc.doc_type
                }
            except Exception as e:
                print(f"Error processing document {doc.doc_type}: {e}")
                continue
        return documents

    def delete(self, *args, **kwargs):
        # Удаляем все документы перед удалением кадета
        for doc in self.documents.all():
            # Удаляем файл из S3
            doc.file.delete()
        super().delete(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['birth_date'])
        ]
        ordering = ['full_name']

class Employee(models.Model):
    full_name = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(2)],
        help_text="Введите полное имя сотрудника"
    )
    birth_date = models.DateField()  # Дата рождения
    position = models.CharField(max_length=255)  # Должность
    experience = models.TextField()  # Опыт работы
    education = models.TextField()  # Образование
    achievements = models.TextField()  # Достижения

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        # Очистка данных перед сохранением
        self.full_name = strip_tags(self.full_name)
        super().save(*args, **kwargs)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    prefix = models.CharField(max_length=10, choices=[
        ('admin', 'Администратор'),
        ('user', 'Пользователь')
    ], default='user')
    allowed_grades = models.CharField(max_length=255, blank=True, null=True, 
        help_text="Классы, доступные для просмотра (через запятую)", default='')
    allowed_tables = models.CharField(max_length=255, blank=True, null=True,
        help_text="Доступные таблицы (cadets и/или employees)", default='')

    def is_admin(self):
        return (
            self.prefix == 'admin' or 
            self.user.is_superuser or 
            'admin' in self.user.username.lower()
        )

    def can_view_grade(self, grade):
        if self.is_admin():
            return True
        if not self.allowed_grades:
            return False
        allowed = [g.strip() for g in self.allowed_grades.split(',') if g.strip()]
        return grade in allowed

    def can_view_table(self, table_name):
        if self.is_admin():
            return True
        if not self.allowed_tables:
            return False
        allowed = [t.strip() for t in self.allowed_tables.split(',') if t.strip()]
        return table_name in allowed

    def __str__(self):
        return f"{self.user.username} - {self.get_prefix_display()}"

class SupportInfo(models.Model):
    email = models.EmailField(verbose_name="Email поддержки")
    telegram = models.CharField(max_length=100, verbose_name="Telegram поддержки")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Информация о поддержке"
        verbose_name_plural = "Информация о поддержке"

    def __str__(self):
        return f"Информация о поддержке (обновлено: {self.updated_at})"

