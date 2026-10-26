from django.shortcuts import render


class LoginRequiredMiddleware:
    """
    Пропускает к сайту только аутентифицированных пользователей.
    Всех остальных — на страницу-заглушку.

    Белый список — служебные пути, без которых нельзя:
    - войти в систему (админка),
    - получить CSS/JS.
    """

    WHITELIST_PREFIXES = (
        "/admin/",      # админка и /admin/login/
        "/static/",     # статика (в dev раздаёт Django)
        "/media/",      # медиа (если появятся)
    )

    WHITELIST_EXACT = (
        "/favicon.ico",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        if any(path.startswith(p) for p in self.WHITELIST_PREFIXES):
            return self.get_response(request)

        if path in self.WHITELIST_EXACT:
            return self.get_response(request)

        if request.user.is_authenticated:
            return self.get_response(request)

        # Не залогинен — страница-заглушка (не показываем содержимое)
        return render(request, "inventory/login_required.html", status=403)