from django.urls import path

from . import views

app_name = 'crawler'

urlpatterns = [
    path('', views.topic_list, name='topic_list'),
    path('topics/create/', views.topic_create, name='topic_create'),
    path('topics/<int:pk>/', views.topic_detail, name='topic_detail'),
    path('topics/<int:pk>/edit/', views.topic_edit, name='topic_edit'),
    path('topics/<int:pk>/delete/', views.topic_delete, name='topic_delete'),
    path('topics/<int:pk>/crawl/', views.topic_crawl, name='topic_crawl'),
    path('pages/', views.page_list, name='page_list'),
    path('pages/<int:pk>/', views.page_detail, name='page_detail'),
    path('pages/<int:pk>/delete/', views.page_delete, name='page_delete'),
    path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
]
