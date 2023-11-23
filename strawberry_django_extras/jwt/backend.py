from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import AnonymousUser

from strawberry_django_extras.jwt.shortcuts import get_user_by_token
from strawberry_django_extras.jwt.utils import get_http_authorization


class JWTBackend(BaseBackend):
    def authenticate(self, request, token=None):
        token = get_http_authorization(request)
        if token is not None:
            return get_user_by_token(token)

        return AnonymousUser()

    def get_user(self, user_id):
        try:
            return get_user_model().objects.get(pk=user_id)
        except get_user_model().DoesNotExist:
            return None
