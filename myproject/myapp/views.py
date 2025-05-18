from .models import Cadet, Employee, CadetDocument, SupportInfo
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.http import url_has_allowed_host_and_scheme  # Изменено здесь
from django.conf import settings
from django.db.models import Q  # Добавляем импорт в начало файла
from django.views.decorators.http import require_http_methods
from django.core.validators import validate_email
from django.utils.html import escape
import logging
import base64
import json
from django.views.decorators.cache import cache_page
from PIL import Image
import io
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.contrib.auth.models import User, Permission
from .models import UserProfile
from django.db.utils import IntegrityError
from django.db import transaction
import os
import uuid

logger = logging.getLogger(__name__)

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        try:
            if form.is_valid():
                user = form.save()
                messages.success(request, 'Аккаунт успешно создан!')
                # Автоматический вход после регистрации
                login(request, user)
                next_url = request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(  # Изменено здесь
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect('cadet_list')
            else:
                for error in form.errors.values():
                    messages.error(request, error)
        except ValidationError as e:
            messages.error(request, str(e))
    else:
        form = UserCreationForm()
    
    return render(request, 'signup.html', {
        'form': form,
        'title': 'Регистрация'
    })

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('cadet_list')  # Перенаправление после успешного входа
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password'})
    return render(request, 'login.html')


@login_required
def cadet_list(request):
    try:
        # Проверяем права доступа к таблице кадетов
        if hasattr(request.user, 'profile'):
            if not request.user.profile.is_admin() and not request.user.profile.can_view_table('cadets'):
                messages.error(request, 'У вас нет прав для просмотра списка кадетов')
                return redirect('home')

        query = request.GET.get('q', '')
        cadets_list = Cadet.objects.prefetch_related('documents')
        
        # Фильтруем по правам доступа к классам только для обычных пользователей
        if hasattr(request.user, 'profile') and not request.user.profile.is_admin():
            allowed_grades = request.user.profile.allowed_grades
            if allowed_grades:
                allowed_grades = [g.strip() for g in allowed_grades.split(',')]
                cadets_list = cadets_list.filter(
                    Q(grade__in=allowed_grades) | Q(grade__isnull=True) | Q(grade='')
                )
        
        if query:
            cadets_list = cadets_list.filter(full_name__icontains=query)
        
        cadets_list = cadets_list.order_by('full_name')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('cadet_list_rows.html', 
                                  {'cadets': cadets_list},
                                  request=request)
            response = HttpResponse(html)
            request.session.save()
            return response
        
        response = render(request, 'cadet_list.html', {'cadets': cadets_list})
        request.session.save()
        return response
        
    except Exception as e:
        logger.error(f"Error in cadet_list view: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': str(e)}, status=500)
        response = render(request, 'cadet_list.html', {'error': str(e)})
        request.session.save()
        return response

def search(request):
    query = request.GET.get('q')
    results = Cadet.objects.filter(title__icontains=query) if query else []
    return render(request, 'search.html', {'results': results})

@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    return redirect('login')

@login_required 
def add_cadet(request):
    if request.method == 'POST':
        try:
            if not request.POST.get('full_name'):
                raise ValidationError('ФИО обязательно для заполнения')

            # Проверяем права доступа для создания кадета с указанным классом
            grade = request.POST.get('grade')
            if hasattr(request.user, 'profile') and not request.user.profile.is_admin():
                if grade:
                    allowed_grades = request.user.profile.allowed_grades
                    if allowed_grades:
                        allowed_grades = [g.strip() for g in allowed_grades.split(',')]
                        if grade not in allowed_grades:
                            raise ValidationError(f'У вас нет прав для создания кадета в классе {grade}')

            # Создаем кадета
            cadet = Cadet(
                full_name=request.POST['full_name'],
                birth_date=request.POST['birth_date'],
                grade=grade,
                personal_info=request.POST.get('personal_info', ''),
                achievements=request.POST.get('achievements', ''),
                reprimands=request.POST.get('reprimands', '')
            )
            
            # Сохраняем кадета (это вызовет clean_grade и валидацию)
            try:
                cadet.save()
            except ValidationError as e:
                messages.error(request, str(e))
                return redirect('cadet_list')

            # Обрабатываем документы
            for doc_type in ['passport', 'registration', 'snils', 'medical']:
                if doc_type in request.FILES:
                    file = request.FILES[doc_type]
                    try:
                        # Обрабатываем изображение
                        processed_image = process_image(file)
                        
                        # Создаем документ
                        new_doc = CadetDocument(
                            cadet=cadet,
                            doc_type=doc_type,
                            filename=f"{doc_type}.{processed_image['extension']}",
                            metadata=processed_image['metadata']
                        )
                        
                        # Сохраняем файл
                        new_doc.file.save(
                            f"{doc_type}.{processed_image['extension']}",
                            ContentFile(processed_image['content'].getvalue()),
                            save=True
                        )
                    except Exception as e:
                        logger.error(f"Error processing document {doc_type}: {e}")
                        raise

            messages.success(request, 'Кадет успешно добавлен')
            return redirect('cadet_list')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            logger.error(f"Error saving cadet: {e}")
            messages.error(request, f'Ошибка при сохранении: {str(e)}')
        
        return redirect('cadet_list')

    return render(request, 'cadet_list.html')

def process_image(file):
    """Обработка изображения и подготовка метаданных"""
    try:
        # Если файл не является изображением, возвращаем его как есть с метаданными
        try:
            img = Image.open(file)
            is_image = True
        except Exception:
            file.seek(0)
            return {
                'content': file,
                'extension': file.name.split('.')[-1].lower(),
                'metadata': {
                    'original_filename': file.name,
                    'content_type': file.content_type if hasattr(file, 'content_type') else None,
                    'size': file.size if hasattr(file, 'size') else None
                }
            }

        # Конвертируем RGBA в RGB если нужно
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img, mask=img.split()[1])
            img = background
        
        # Определяем формат файла
        format_mapping = {
            'JPEG': 'jpg',
            'PNG': 'png',
            'GIF': 'gif',
            'BMP': 'bmp',
            'WEBP': 'webp'
        }
        
        original_extension = file.name.split('.')[-1].lower()
        if original_extension in format_mapping.values():
            img_format = next((k for k, v in format_mapping.items() if v == original_extension), 'JPEG')
        else:
            img_format = img.format if img.format in format_mapping else 'JPEG'
        
        extension = format_mapping.get(img_format, 'jpg').lower()
        
        # Сохраняем изображение
        output = io.BytesIO()
        if img_format == 'JPEG':
            img.save(output, format=img_format, quality=85, optimize=True)
        else:
            img.save(output, format=img_format, optimize=True)
        
        output.seek(0)
        
        # Собираем метаданные изображения
        metadata = {
            'original_filename': file.name,
            'content_type': file.content_type if hasattr(file, 'content_type') else f'image/{extension}',
            'size': output.getbuffer().nbytes,
            'dimensions': img.size,
            'format': img_format,
            'mode': img.mode
        }
        
        return {
            'content': output,
            'extension': extension,
            'metadata': metadata
        }
        
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise

@login_required
def edit_cadet(request, cadet_id):
    try:
        cadet = get_object_or_404(Cadet, id=cadet_id)
        
        # Проверяем права доступа для редактирования кадета
        if hasattr(request.user, 'profile') and not request.user.profile.is_admin():
            allowed_grades = request.user.profile.allowed_grades
            if allowed_grades:
                allowed_grades = [g.strip() for g in allowed_grades.split(',')]
                if cadet.grade not in allowed_grades:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'У вас нет прав для редактирования этого кадета'
                    })
        
        if request.method == 'POST':
            # Проверяем права доступа для нового класса
            new_grade = request.POST.get('grade')
            if hasattr(request.user, 'profile') and not request.user.profile.is_admin():
                if new_grade:
                    allowed_grades = request.user.profile.allowed_grades
                    if allowed_grades:
                        allowed_grades = [g.strip() for g in allowed_grades.split(',')]
                        if new_grade not in allowed_grades:
                            return JsonResponse({
                                'status': 'error',
                                'message': f'У вас нет прав для перевода кадета в класс {new_grade}'
                            })

            # Обновляем основные данные
            cadet.full_name = request.POST['full_name']
            cadet.birth_date = request.POST['birth_date']
            cadet.grade = new_grade
            cadet.personal_info = request.POST.get('personal_info', '')
            cadet.achievements = request.POST.get('achievements', '')
            cadet.reprimands = request.POST.get('reprimands', '')
            
            try:
                cadet.save()
            except ValidationError as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                })

            # Обработка документов
            doc_types = ['passport', 'registration', 'snils', 'medical']
            for doc_type in doc_types:
                file_key = f'{doc_type}_file'
                metadata_key = f'{doc_type}_metadata'
                
                if file_key in request.FILES:
                    file = request.FILES[file_key]
                    try:
                        metadata = json.loads(request.POST.get(metadata_key, '{}'))
                    except json.JSONDecodeError:
                        metadata = {}
                    
                    try:
                        # Удаляем старый документ если есть
                        try:
                            old_doc = CadetDocument.objects.filter(cadet=cadet, doc_type=doc_type).first()
                            if old_doc:
                                try:
                                    # Сначала удаляем файл из хранилища
                                    old_doc.file.delete(save=False)
                                except Exception as e:
                                    logger.error(f"Error deleting file from storage: {e}")
                                # Затем удаляем запись из базы данных
                                old_doc.delete()
                        except Exception as e:
                            logger.error(f"Error handling old document: {e}")
                        
                        # Обрабатываем изображение
                        processed_image = process_image(file)
                        
                        # Создаем новый документ
                        new_doc = CadetDocument(
                            cadet=cadet,
                            doc_type=doc_type,
                            filename=f"{cadet.id}_{doc_type}.{processed_image['extension']}",
                            metadata=metadata
                        )
                        
                        # Сохраняем файл
                        file_name = f"{cadet.id}_{doc_type}.{processed_image['extension']}"
                        new_doc.file.save(
                            file_name,
                            ContentFile(processed_image['content'].getvalue()),
                            save=True
                        )
                        
                        logger.info(f"Successfully saved document {doc_type} for cadet {cadet.id}")
                        
                    except Exception as e:
                        logger.error(f"Error processing document {doc_type}: {str(e)}", exc_info=True)
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Ошибка при обработке документа {doc_type}: {str(e)}'
                        })

            return JsonResponse({'status': 'success'})
            
    except Exception as e:
        logger.error(f"Error in edit_cadet view: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Ошибка при редактировании кадета: {str(e)}'
        })

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def delete_cadet(request, cadet_id):
    try:
        cadet = get_object_or_404(Cadet, id=cadet_id)
        if request.method == 'POST':
            # Удаляем кадета (метод delete в модели позаботится об удалении файлов)
            cadet.delete()
            return redirect('cadet_list')
    except Exception as e:
        print(f"Error deleting cadet: {e}")
        messages.error(request, f'Ошибка при удалении кадета: {str(e)}')
    
    return redirect('cadet_list')

@require_http_methods(["POST"])
@login_required
def add_employee(request):
    try:
        # Санитизация входных данных
        full_name = escape(request.POST.get('full_name', ''))
        if not full_name:
            raise ValidationError('ФИО обязательно')
            
        # Логирование действий
        logger.info(f'User {request.user} adding employee: {full_name}')
        
        # Существующий код...
        Employee.objects.create(
            full_name=request.POST['full_name'],
            birth_date=request.POST['birth_date'],
            position=request.POST['position'],
            experience=request.POST['experience'],
            education=request.POST['education'],
            achievements=request.POST['achievements']
        )
        next_url = request.POST.get('next', 'employee_list')
        return redirect(next_url)
    except Exception as e:
        logger.error(f'Error adding employee: {str(e)}')
        messages.error(request, 'Ошибка при добавлении сотрудника')
        return redirect('employee_list')

@login_required
def edit_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        try:
            employee.full_name = request.POST['full_name']
            employee.birth_date = request.POST['birth_date']
            employee.position = request.POST['position']
            employee.experience = request.POST['experience']
            employee.education = request.POST['education']
            employee.achievements = request.POST['achievements']
            employee.save()
            next_url = request.GET.get('next', 'employee_list')
            return redirect(next_url)
        except Exception as e:
            print(f"Error editing employee: {e}")
            return render(request, 'cadet_list.html', {
                'error': str(e),
                'employees': Employee.objects.all(),
                'cadets': Cadet.objects.all()
            })
    
    return render(request, 'cadet_list.html', {
        'employees': Employee.objects.all(),
        'cadets': Cadet.objects.all()
    })

@login_required
def delete_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if request.method == 'POST':
        try:
            employee.delete()
            next_url = request.GET.get('next', 'employee_list')
            return redirect(next_url)
        except Exception as e:
            print(f"Error deleting employee: {e}")
            return render(request, 'cadet_list.html', {
                'error': str(e),
                'employees': Employee.objects.all(),
                'cadets': Cadet.objects.all()
            })
    return redirect('cadet_list')

@login_required
def employee_list(request):
    try:
        # Проверяем права доступа к таблице сотрудников
        if hasattr(request.user, 'profile'):
            if not request.user.profile.is_admin() and not request.user.profile.can_view_table('employees'):
                messages.error(request, 'У вас нет прав для просмотра списка сотрудников')
                return redirect('home')

        query = request.GET.get('q', '').strip()
        employees = Employee.objects.all()
        
        if query:
            employees = employees.filter(
                Q(full_name__contains=query) |  
                Q(position__contains=query)    
            )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('employee_list_rows.html', {
                'employees': employees
            })
            return HttpResponse(html)
        
        return render(request, 'employee_list.html', {
            'employees': employees,
            'query': query
        })
        
    except Exception as e:
        messages.error(request, f'Ошибка при поиске сотрудников: {str(e)}')
        return render(request, 'employee_list.html', {
            'employees': Employee.objects.all(),
            'error': str(e)
        })

@login_required
def get_cadet_documents(request, cadet_id):
    try:
        cadet = get_object_or_404(Cadet, id=cadet_id)
        documents = {}
        
        for doc in cadet.documents.all():
            try:
                # Возвращаем только URL файла и метаданные, не пытаемся открыть файл
                documents[doc.doc_type] = {
                    'url': doc.file_url,
                    'name': doc.filename,
                    'type': doc.doc_type,
                    'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if doc.uploaded_at else None,
                    'size': doc.file_size_formatted
                }
            except Exception as e:
                logger.error(f"Error processing document {doc.doc_type}: {e}")
                continue
        
        return JsonResponse(documents)
    except Exception as e:
        logger.error(f"Error in get_cadet_documents: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def delete_cadet_document(request, cadet_id, doc_type):
    if request.method == 'POST':
        try:
            cadet = get_object_or_404(Cadet, id=cadet_id)
            doc = get_object_or_404(CadetDocument, cadet=cadet, doc_type=doc_type)
            
            try:
                doc.file.delete()
            except Exception as e:
                logger.error(f"Error deleting document file: {e}")
            
            doc.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error in delete_cadet_document: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

def compress_image(image_file):
    img = Image.open(image_file)
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=70, optimize=True)
    output.seek(0)
    return output

@login_required
@require_http_methods(["POST"])
def upload_document(request):
    try:
        cadet_id = request.POST.get('cadet_id')
        doc_type = request.POST.get('doc_type')
        file = request.FILES.get('file')

        if not all([cadet_id, doc_type, file]):
            return JsonResponse({
                'status': 'error',
                'message': 'Не все необходимые данные предоставлены'
            }, status=400)

        cadet = get_object_or_404(Cadet, id=cadet_id)

        try:
            # Пытаемся найти существующий документ
            existing_doc = CadetDocument.objects.filter(cadet=cadet, doc_type=doc_type).first()
            
            if existing_doc:
                # Если документ существует, удаляем старый файл
                try:
                    existing_doc.file.delete(save=False)
                except Exception as e:
                    logger.error(f"Error deleting old file: {e}")
                
                # Создаем новый документ вместо обновления существующего
                existing_doc.delete()

            # Получаем расширение файла
            _, ext = os.path.splitext(file.name)
            
            # Создаем безопасное имя файла без кириллицы
            safe_filename = f"{uuid.uuid4().hex}{ext}"
            
            # Создаем новый документ с оригинальным именем в поле filename
            new_doc = CadetDocument(
                cadet=cadet,
                doc_type=doc_type,
                filename=file.name
            )
            
            # Сохраняем файл с безопасным именем
            new_doc.file.save(safe_filename, file, save=True)

            return JsonResponse({
                'status': 'success',
                'message': 'Документ успешно загружен',
                'document': {
                    'id': new_doc.id,
                    'filename': new_doc.filename,
                    'url': new_doc.file.url
                }
            })

        except IntegrityError as e:
            logger.error(f"Integrity error in upload_document: {e}")
            return JsonResponse({
                'status': 'error',
                'message': 'Документ такого типа уже существует'
            }, status=400)

    except Exception as e:
        logger.error(f"Error in upload_document: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def create_user(request):
    # Проверяем, является ли пользователь администратором
    if not hasattr(request.user, 'profile') or not request.user.profile.is_admin():
        messages.error(request, 'У вас нет прав для создания пользователей')
        return redirect('cadet_list')
    
    if request.method == 'POST':
        try:
            username = request.POST.get('username')
            password = request.POST.get('password')
            prefix = request.POST.get('prefix')
            
            # Проверяем, не существует ли уже такой пользователь
            if User.objects.filter(username=username).exists():
                raise ValidationError('Пользователь с таким именем уже существует')
            
            with transaction.atomic():
                # Создаем пользователя
                user = User.objects.create_user(username=username, password=password)
                
                # Обрабатываем разрешения в зависимости от типа пользователя
                if prefix == 'admin':
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()
                    
                    # Создаем профиль администратора
                    profile = UserProfile.objects.create(
                        user=user,
                        prefix='admin',
                        allowed_grades='',
                        allowed_tables='cadets,employees'
                    )
                else:
                    # Получаем и очищаем список разрешенных классов
                    allowed_grades = request.POST.get('allowed_grades', '').strip()
                    if allowed_grades:
                        # Очищаем и нормализуем список классов
                        grades = []
                        for grade in allowed_grades.split(','):
                            grade = grade.strip()
                            if grade:
                                # Удаляем все пробелы и приводим к верхнему регистру
                                grade = ''.join(grade.split()).upper()
                                # Проверяем формат класса (число + буква)
                                if any(char.isdigit() for char in grade) and any(char.isalpha() for char in grade):
                                    grades.append(grade)
                        allowed_grades = ','.join(grades) if grades else ''
                    
                    # Получаем выбранные таблицы
                    allowed_tables = []
                    if request.POST.get('can_view_cadets'):
                        allowed_tables.append('cadets')
                    if request.POST.get('can_view_employees'):
                        allowed_tables.append('employees')
                    
                    # Если таблицы не выбраны, даем доступ хотя бы к кадетам
                    if not allowed_tables:
                        allowed_tables = ['cadets']
                    
                    # Создаем профиль обычного пользователя
                    profile = UserProfile.objects.create(
                        user=user,
                        prefix='user',
                        allowed_grades=allowed_grades,
                        allowed_tables=','.join(allowed_tables)
                    )
            
            messages.success(request, f'Пользователь {username} успешно создан')
            return redirect('user_list')
            
        except ValidationError as e:
            messages.error(request, str(e))
        except IntegrityError as e:
            logger.error(f"Integrity error creating user: {str(e)}")
            # Если произошла ошибка, удаляем пользователя, если он был создан
            if 'user' in locals():
                user.delete()
            messages.error(request, 'Ошибка при создании пользователя: возможно, профиль уже существует')
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            # Если произошла ошибка, удаляем пользователя, если он был создан
            if 'user' in locals():
                user.delete()
            messages.error(request, f'Ошибка при создании пользователя: {str(e)}')
            
    return render(request, 'create_user.html', {
        'prefixes': [('admin', 'Администратор'), ('user', 'Пользователь')]
    })

@login_required
def update_admin_permissions(request):
    if not request.user.is_superuser:
        messages.error(request, 'Только суперпользователь может обновлять права администраторов')
        return redirect('cadet_list')
        
    try:
        # Получаем всех пользователей с префиксом admin
        admin_profiles = UserProfile.objects.filter(prefix='admin')
        
        for profile in admin_profiles:
            user = profile.user
            # Устанавливаем базовые права администратора
            user.is_staff = True
            user.is_superuser = True
            # Добавляем все возможные права
            user.user_permissions.add(*Permission.objects.all())
            user.save()
            
            # Обновляем профиль
            profile.allowed_grades = None
            profile.allowed_tables = None
            profile.save()
            
        messages.success(request, 'Права администраторов успешно обновлены')
    except Exception as e:
        messages.error(request, f'Ошибка при обновлении прав: {str(e)}')
        
    return redirect('cadet_list')

@login_required
def update_admin_user(request):
    try:
        # Получаем пользователя admin
        admin_user = User.objects.get(username='admin')
        
        # Устанавливаем базовые права администратора
        admin_user.is_staff = True
        admin_user.is_superuser = True
        
        # Добавляем все возможные права
        admin_user.user_permissions.add(*Permission.objects.all())
        admin_user.save()
        
        # Получаем или создаем профиль
        profile, created = UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={
                'prefix': 'admin',
                'allowed_grades': None,
                'allowed_tables': None
            }
        )
        
        if not created:
            profile.prefix = 'admin'
            profile.allowed_grades = None
            profile.allowed_tables = None
            profile.save()
        
        messages.success(request, 'Права пользователя admin успешно обновлены')
        
    except User.DoesNotExist:
        messages.error(request, 'Пользователь admin не найден')
    except Exception as e:
        messages.error(request, f'Ошибка при обновлении прав: {str(e)}')
        
    return redirect('cadet_list')

@login_required
def user_list(request):
    # Проверяем, является ли пользователь администратором
    if not request.user.profile.is_admin():
        messages.error(request, 'У вас нет прав для просмотра списка пользователей')
        return redirect('cadet_list')
    
    users = User.objects.select_related('profile').all()
    return render(request, 'user_list.html', {'users': users})

@login_required
def edit_user(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.is_admin():
        messages.error(request, 'У вас нет прав для редактирования пользователей')
        return redirect('cadet_list')
    
    if request.method == 'POST':
        try:
            # Логируем все входящие данные
            logger.info("Editing user with POST data: %s", request.POST)
            
            user_id = request.POST.get('user_id')
            user = User.objects.get(id=user_id)
            profile = user.profile
            
            logger.info("Current user profile state - allowed_grades: %s, allowed_tables: %s", 
                       profile.allowed_grades, profile.allowed_tables)
            
            # Обновляем имя пользователя
            new_username = request.POST.get('username')
            if new_username != user.username:
                if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                    raise ValidationError('Пользователь с таким именем уже существует')
            
            with transaction.atomic():
                if new_username != user.username:
                    user.username = new_username
                
                # Обновляем пароль, если он был предоставлен
                password = request.POST.get('password')
                if password:
                    user.set_password(password)
                
                # Обновляем тип пользователя и права
                prefix = request.POST.get('prefix')
                logger.info("User type (prefix): %s", prefix)
                
                if prefix == 'admin':
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()
                    profile.prefix = prefix
                    profile.allowed_grades = ''
                    profile.allowed_tables = 'cadets,employees'
                    logger.info("Setting admin privileges")
                else:
                    user.is_staff = False
                    user.is_superuser = False
                    user.save()
                    profile.prefix = prefix
                    
                    # Обрабатываем список классов
                    allowed_grades = request.POST.get('allowed_grades', '').strip()
                    logger.info("Processing allowed grades: %s", allowed_grades)
                    
                    if allowed_grades:
                        # Очищаем и нормализуем список классов
                        grades = []
                        for grade in allowed_grades.split(','):
                            grade = grade.strip()
                            if grade:
                                # Удаляем все пробелы и приводим к верхнему регистру
                                grade = ''.join(grade.split()).upper()
                                # Проверяем формат класса (число + буква)
                                if any(char.isdigit() for char in grade) and any(char.isalpha() for char in grade):
                                    grades.append(grade)
                                    logger.info("Added grade: %s", grade)
                                else:
                                    logger.warning("Invalid grade format: %s", grade)
                        
                        profile.allowed_grades = ','.join(grades) if grades else ''
                        logger.info("Final allowed_grades: %s", profile.allowed_grades)
                    else:
                        profile.allowed_grades = ''
                        logger.info("No grades provided")
                    
                    # Обновляем доступные таблицы
                    allowed_tables = []
                    if request.POST.get('can_view_cadets'):
                        allowed_tables.append('cadets')
                    if request.POST.get('can_view_employees'):
                        allowed_tables.append('employees')
                    profile.allowed_tables = ','.join(allowed_tables) if allowed_tables else 'cadets'
                    logger.info("Setting allowed_tables: %s", profile.allowed_tables)
                
                # Сохраняем профиль и проверяем результат
                profile.save()
                logger.info("Profile saved. Final state - allowed_grades: %s, allowed_tables: %s", 
                           profile.allowed_grades, profile.allowed_tables)
                
                # Проверяем, что изменения действительно сохранились
                profile.refresh_from_db()
                logger.info("Profile after refresh - allowed_grades: %s, allowed_tables: %s", 
                           profile.allowed_grades, profile.allowed_tables)
            
            messages.success(request, 'Пользователь успешно обновлен')
            
        except User.DoesNotExist:
            logger.error("User with id %s not found", user_id)
            messages.error(request, 'Пользователь не найден')
        except ValidationError as e:
            logger.error("Validation error: %s", str(e))
            messages.error(request, str(e))
        except IntegrityError as e:
            logger.error("Integrity error updating user: %s", str(e))
            messages.error(request, 'Ошибка при обновлении пользователя: возможно, профиль уже существует')
        except Exception as e:
            logger.error("Error updating user: %s", str(e), exc_info=True)
            messages.error(request, f'Ошибка при обновлении пользователя: {str(e)}')
    
    return redirect('user_list')

@login_required
def delete_user(request):
    if not request.user.profile.is_admin():
        messages.error(request, 'У вас нет прав для удаления пользователей')
        return redirect('cadet_list')
    
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            user = User.objects.get(id=user_id)
            
            # Запрещаем удалять пользователя admin
            if user.username == 'admin':
                messages.error(request, 'Невозможно удалить главного администратора')
                return redirect('user_list')
            
            username = user.username
            user.delete()
            messages.success(request, f'Пользователь {username} успешно удален')
            
        except User.DoesNotExist:
            messages.error(request, 'Пользователь не найден')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении пользователя: {str(e)}')
    
    return redirect('user_list')

@login_required
def update_support_info(request):
    if not request.user.profile.is_admin:
        messages.error(request, "У вас нет прав для выполнения этого действия")
        return redirect('cadet_list')

    if request.method == 'POST':
        support_info = SupportInfo.objects.first()
        if not support_info:
            support_info = SupportInfo()
        
        support_info.email = request.POST.get('support_email', '')
        support_info.telegram = request.POST.get('support_telegram', '')
        support_info.save()
        
        messages.success(request, "Информация о поддержке обновлена")
        return redirect(request.META.get('HTTP_REFERER', 'cadet_list'))

    return redirect('cadet_list')

@login_required
def search_users(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    query = request.GET.get('q', '').strip()
    users = User.objects.select_related('profile').all()
    
    if query:
        users = users.filter(username__icontains=query)
    
    html = render_to_string('user_list_rows.html', {'users': users}, request=request)
    return JsonResponse({'html': html})
