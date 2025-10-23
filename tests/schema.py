from typing import cast

import strawberry
import strawberry_django
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from strawberry import relay
from strawberry.types.info import Info
from strawberry_django.auth.queries import get_current_user
from strawberry_django.optimizer import (
    DjangoOptimizerExtension,
)

UserModel = get_user_model()



@strawberry_django.type(UserModel)
class UserType(relay.Node):
    id: relay.NodeID[int]
    username: strawberry.auto
    email: strawberry.auto
    is_active: strawberry.auto
    is_superuser: strawberry.auto
    is_staff: strawberry.auto

    @strawberry_django.field(only=["first_name", "last_name"])
    def full_name(self, root: AbstractUser) -> str:
        return f"{root.first_name or ''} {root.last_name or ''}".strip()

@strawberry.type
class Query:
    """All available queries for this schema."""
    @strawberry_django.field
    def me(self, info: Info) -> UserType | None:
        user = get_current_user(info, strict=True)
        if not user.is_authenticated:
            return None

        return cast("UserType", user)


@strawberry.type
class Mutation:
    """All available mutations for this schema."""


schema = strawberry.Schema(
    query=Query,
    extensions=[
        DjangoOptimizerExtension,
    ],
)
