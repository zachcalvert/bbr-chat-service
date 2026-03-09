from django.shortcuts import redirect
from django.conf import settings


class LoginRequiredMiddleware:
    EXEMPT_URLS = [
        settings.LOGIN_URL,
        '/admin/',
        '/chat/api/',
        '/groupme/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            if not any(request.path.startswith(url) for url in self.EXEMPT_URLS):
                return redirect(f'{settings.LOGIN_URL}?next={request.path}')
        return self.get_response(request)
