"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from myapp import views  # Импортируем views из myapp
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.cadet_list, name='home'),
    path('cadets/', views.cadet_list, name='cadet_list'),
    path('employees/', views.employee_list, name='employee_list'),
    path('add-cadet/', views.add_cadet, name='add_cadet'),
    path('edit-cadet/<int:cadet_id>/', views.edit_cadet, name='edit_cadet'),
    path('delete-cadet/<int:cadet_id>/', views.delete_cadet, name='delete_cadet'),
    path('edit-cadet/<int:cadet_id>/documents/', views.get_cadet_documents, name='get_cadet_documents'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),  # next_page — страница, на которую вы хотите перенаправить после logout
    path('signup/', views.signup, name='signup'),  # Пример для signup
    path('search/', views.search, name='search'),  # Пример для поиска
    path('add-employee/', views.add_employee, name='add_employee'),
    path('edit-employee/<int:employee_id>/', views.edit_employee, name='edit_employee'),
    path('delete-employee/<int:employee_id>/', views.delete_employee, name='delete_employee'),
    path('get-cadet-documents/<int:cadet_id>/', views.get_cadet_documents, name='get_cadet_documents'),
    path('delete-cadet-document/<int:cadet_id>/<str:doc_type>/', views.delete_cadet_document, name='delete_cadet_document'),
    path('upload-document/', views.upload_document, name='upload_document'),  # Новый URL для загрузки документов
    path('create-user/', views.create_user, name='create_user'),
    path('update-admin-permissions/', views.update_admin_permissions, name='update_admin_permissions'),
    path('update-admin-user/', views.update_admin_user, name='update_admin_user'),
    path('users/', views.user_list, name='user_list'),
    path('users/edit/', views.edit_user, name='edit_user'),
    path('users/delete/', views.delete_user, name='delete_user'),
    path('users/search/', views.search_users, name='search_users'),  # Перемещаем URL поиска в группу users
    path('update-support-info/', views.update_support_info, name='update_support_info'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]