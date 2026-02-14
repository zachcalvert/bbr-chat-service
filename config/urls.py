from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('knowledge/', include('apps.knowledge.urls')),
    path('crawler/', include('apps.crawler.urls')),
    path('chat/', include('apps.chat.urls')),
]
