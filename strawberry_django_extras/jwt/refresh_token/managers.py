from django.db import models
from django.db.models import Case, When
from django.db.models import Value as Val
from django.utils import timezone

from strawberry_django_extras.jwt.settings import jwt_settings


class RefreshTokenQuerySet(models.QuerySet):
    def expired(self):
        expires = timezone.now() - jwt_settings.JWT_REFRESH_EXPIRATION_DELTA
        return self.annotate(
            expired=Case(
                When(created__lt=expires, then=Val(True)),
                output_field=models.BooleanField(),
                default=Val(False),
            ),
        )
