from django.urls import path

from . import views

app_name = 'groupme'

urlpatterns = [
    path('callback/', views.groupme_callback, name='callback'),
]
