import asyncio
from calendar import timegm
from datetime import datetime

import jwt
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from .exceptions import JSONWebTokenError, JSONWebTokenExpired
from .settings import jwt_settings


def jwt_payload(user):
    username = user.get_username()

    if hasattr(username, "pk"):
        username = username.pk

    exp = datetime.utcnow() + jwt_settings.JWT_EXPIRATION_DELTA

    payload = {
        user.USERNAME_FIELD: username,
        "exp": timegm(exp.utctimetuple()),
    }

    if jwt_settings.JWT_ALLOW_REFRESH:
        payload["origIat"] = timegm(datetime.utcnow().utctimetuple())

    if jwt_settings.JWT_AUDIENCE is not None:
        payload["aud"] = jwt_settings.JWT_AUDIENCE

    if jwt_settings.JWT_ISSUER is not None:
        payload["iss"] = jwt_settings.JWT_ISSUER

    return payload


def jwt_encode(payload):
    return jwt.encode(
        payload,
        jwt_settings.JWT_PRIVATE_KEY or jwt_settings.JWT_SECRET_KEY,
        jwt_settings.JWT_ALGORITHM,
    )


def jwt_decode(token):
    return jwt.decode(
        token,
        jwt_settings.JWT_PUBLIC_KEY or jwt_settings.JWT_SECRET_KEY,
        options={
            "verify_exp": jwt_settings.JWT_VERIFY_EXPIRATION,
            "verify_aud": jwt_settings.JWT_AUDIENCE is not None,
            "verify_signature": jwt_settings.JWT_VERIFY,
        },
        leeway=jwt_settings.JWT_LEEWAY,
        audience=jwt_settings.JWT_AUDIENCE,
        issuer=jwt_settings.JWT_ISSUER,
        algorithms=[jwt_settings.JWT_ALGORITHM],
    )


def get_http_authorization(request):
    auth = request.META.get(jwt_settings.JWT_AUTH_HEADER_NAME, "").split()
    prefix = jwt_settings.JWT_AUTH_HEADER_PREFIX

    if len(auth) != 2 or auth[0].lower() != prefix.lower():
        return None
    return auth[1]


def get_credentials(request):
    return get_http_authorization(request)


def get_payload(token, context=None):
    try:
        payload = jwt_settings.JWT_DECODE_HANDLER(token)
    except jwt.ExpiredSignatureError:
        raise JSONWebTokenExpired()
    except jwt.DecodeError:
        raise JSONWebTokenError(_("Error decoding signature"))
    except jwt.InvalidTokenError:
        raise JSONWebTokenError(_("Invalid token"))
    return payload


def get_user_by_natural_key(username):
    user_model = get_user_model()
    try:
        return user_model.objects.get_by_natural_key(username)
    except user_model.DoesNotExist:
        return None


def get_user_by_payload(payload):
    username = jwt_settings.JWT_PAYLOAD_GET_USERNAME_HANDLER(payload)

    if not username:
        raise JSONWebTokenError(_("Invalid payload"))

    user = jwt_settings.JWT_GET_USER_BY_NATURAL_KEY_HANDLER(username)

    if user is not None and not getattr(user, "is_active", True):
        raise JSONWebTokenError(_("User is disabled"))
    return user


def refresh_has_expired(orig_iat):
    exp = orig_iat + jwt_settings.JWT_REFRESH_EXPIRATION_DELTA.total_seconds()
    return timegm(datetime.utcnow().utctimetuple()) > exp


def is_async() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    else:
        return True
