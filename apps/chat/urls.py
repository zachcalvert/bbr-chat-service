from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.conversation_list, name='list'),
    path('new/', views.conversation_new, name='new'),
    path('<int:pk>/', views.conversation_view, name='conversation'),
    path('<int:pk>/delete/', views.conversation_delete, name='delete'),
    path('<int:pk>/send/', views.send_message, name='send'),
    path('<int:pk>/voice/', views.conversation_set_voice, name='set_voice'),
    path('api/query/', views.groupme_query, name='api_query'),
]
