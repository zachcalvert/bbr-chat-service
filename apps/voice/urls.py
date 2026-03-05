from django.urls import path

from . import views

app_name = 'voice'

urlpatterns = [
    path('', views.member_list, name='member_list'),
    path('<int:pk>/', views.member_detail, name='member_detail'),
]
