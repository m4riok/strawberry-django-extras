from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RefreshTokenConfig(AppConfig):
    name = "strawberry_django_extras.jwt.refresh_token"
    label = "refresh_token"
    verbose_name = _("Refresh token")
