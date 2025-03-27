# middleware.py
class RoleValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.role:
            request.user.role = 'viewer'
            request.user.save()
        return self.get_response(request)


# middleware.py
from django.http import HttpResponseForbidden


class PermissionDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 403 and request.user.is_authenticated:
            debug_info = (
                f"User: {request.user.username} | "
                f"Role: {request.user.role} | "
                f"Superuser: {request.user.is_superuser}"
            )
            response.content = f"{response.content.decode()} | {debug_info}"

        return response