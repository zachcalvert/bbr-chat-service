from django.urls import path

from . import views

app_name = 'knowledge'

urlpatterns = [
    path('', views.knowledge_list, name='list'),
    path('create/', views.knowledge_create, name='create'),
    path('<int:pk>/', views.knowledge_detail, name='detail'),
    path('<int:pk>/edit/', views.knowledge_edit, name='edit'),
    path('<int:pk>/delete/', views.knowledge_delete, name='delete'),
]
