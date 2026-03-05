from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('apps.core.urls')),
    path('knowledge/', include('apps.knowledge.urls')),
    path('crawler/', include('apps.crawler.urls')),
    path('chat/', include('apps.chat.urls')),
    path('voice/', include('apps.voice.urls')),
]
