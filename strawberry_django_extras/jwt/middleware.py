from asgiref.sync import iscoroutinefunction, sync_to_async
from django.contrib import auth
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.utils.decorators import sync_and_async_middleware

from strawberry_django_extras.jwt.exceptions import JSONWebTokenError, JSONWebTokenExpired


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
                return HttpResponse("Token expired", status=401)
            except JSONWebTokenError:
                return HttpResponse("Invalid token", status=401)
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
                return HttpResponse("Token expired", status=401)
            except JSONWebTokenError:
                return HttpResponse("Invalid token", status=401)
            return get_response(request)

    return middleware
