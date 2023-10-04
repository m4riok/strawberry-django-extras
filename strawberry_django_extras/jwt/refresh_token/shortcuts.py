from django.utils.functional import lazy
from django.utils.translation import gettext as _

from strawberry_django_extras.jwt.exceptions import JSONWebTokenError
from strawberry_django_extras.jwt.refresh_token.models import AbstractRefreshToken
from strawberry_django_extras.jwt.refresh_token.utils import get_refresh_token_model
from strawberry_django_extras.jwt.settings import jwt_settings


def get_refresh_token(token, context=None):
    refresh_token_model = get_refresh_token_model()

    try:
        return jwt_settings.JWT_GET_REFRESH_TOKEN_HANDLER(
            refresh_token_model=refresh_token_model,
            token=token,
            context=context,
        )

    except refresh_token_model.DoesNotExist:
        raise JSONWebTokenError(_("Invalid refresh token")) from None


def create_refresh_token(user, refresh_token=None) -> AbstractRefreshToken:
    if refresh_token is not None and jwt_settings.JWT_REUSE_REFRESH_TOKENS:
        refresh_token.reuse()
        return refresh_token
    return get_refresh_token_model().objects.create(user=user)


def get_refresh_token_user(refresh_token):
    return refresh_token.user


refresh_token_lazy = lazy(
    lambda user, refresh_token=None: create_refresh_token(user, refresh_token).get_token(),
    str,
)
