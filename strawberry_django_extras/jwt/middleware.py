
from typing import TYPE_CHECKING

from asgiref.sync import iscoroutinefunction, sync_to_async
from django.contrib import auth
from django.contrib.auth import authenticate
from django.http import HttpRequest, HttpResponse
from django.utils.decorators import sync_and_async_middleware

from strawberry_django_extras.jwt.exceptions import (
    JSONWebTokenError,
    JSONWebTokenExpired,
)
from strawberry_django_extras.jwt.settings import jwt_settings

if TYPE_CHECKING:
    from collections.abc import Callable


def get_unauthorized_response(
    request: HttpRequest, exception: Exception
) -> HttpResponse:
    """Get an unauthorized response using the configured handler."""
    handler: Callable[[HttpRequest, Exception], HttpResponse] = jwt_settings.JWT_UNAUTHORIZED_RESPONSE_HANDLER  # type: ignore[assignment]
    return handler(request=request, exception=exception)


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
            except (JSONWebTokenExpired, JSONWebTokenError) as e:
                return get_unauthorized_response(request, e)
            return await get_response(request)

    else:

        def middleware(request):
            try:
                user = auth.get_user(request)
                if user.is_anonymous or user is None:
                    auth_user = authenticate(request)
                    if auth_user is not None:
                        request.user = auth_user
            except (JSONWebTokenExpired, JSONWebTokenError) as e:
                return get_unauthorized_response(request, e)
            return get_response(request)

    return middleware
