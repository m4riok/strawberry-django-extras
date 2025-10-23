from asgiref.sync import iscoroutinefunction, sync_to_async
from django.contrib import auth
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.utils.decorators import sync_and_async_middleware

from strawberry_django_extras.jwt.exceptions import (
    JSONWebTokenError,
    JSONWebTokenExpired,
)

TOKEN_EXPIRED_ERROR_MESSAGE = "Token expired"
INVALID_TOKEN_ERROR_MESSAGE = "Invalid token"


class ResponseUnauthorized(JsonResponse):
    status_code = 401

    def __init__(self, message="Unauthorized"):
        error = {
            "message": message,
            "code": "unauthorized",
            "hint": "Either use Valid Token or make requests without token.",
        }
        super().__init__({"errors": [error]})


@sync_and_async_middleware
def jwt_middleware(get_response):
    if iscoroutinefunction(get_response):

        async def middleware(request):
            try:
                user = await sync_to_async(auth.get_user)(request)
                if user.is_anonymous or user is None:
                    auth_user = await sync_to_async(authenticate)(request)
                    if auth_user is not None:
                        request.user = auth_user
            except JSONWebTokenExpired:
                return ResponseUnauthorized(TOKEN_EXPIRED_ERROR_MESSAGE)
            except JSONWebTokenError:
                return ResponseUnauthorized(INVALID_TOKEN_ERROR_MESSAGE)
            return await get_response(request)

    else:

        def middleware(request):
            try:
                user = auth.get_user(request)
                if user.is_anonymous or user is None:
                    auth_user = authenticate(request)
                    if auth_user is not None:
                        request.user = auth_user
            except JSONWebTokenExpired:
                return ResponseUnauthorized(TOKEN_EXPIRED_ERROR_MESSAGE)
            except JSONWebTokenError:
                return ResponseUnauthorized(INVALID_TOKEN_ERROR_MESSAGE)
            return get_response(request)

    return middleware
