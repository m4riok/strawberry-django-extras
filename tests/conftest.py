from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.test.client import AsyncClient, Client
from strawberry_django.optimizer import DjangoOptimizerExtension

from tests.utils import GraphQLTestClient

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


User = get_user_model()

@pytest.mark.django_db(transaction=True)
@pytest.fixture
def user() -> AbstractUser:
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def valid_token(user: AbstractUser) -> str:
    """Generate a valid JWT token for the test user."""
    from strawberry_django_extras.jwt.shortcuts import get_token

    return get_token(user)


@pytest.fixture
def graphql_client():
    """Create a GraphQL test client."""
    with GraphQLTestClient("/graphql/", Client()) as client:
        yield client


@pytest.fixture(params=["sync", "async", "sync_no_optimizer", "async_no_optimizer"])
def gql_client(request):
    """Parameterized GraphQL client supporting sync/async and optimizer on/off.
    """
    from typing import cast

    client_class, path, with_optimizer = cast(
        "dict[str, tuple[type[Client | AsyncClient], str, bool]]",
        {
            "sync": (Client, "/graphql/", True),
            "async": (AsyncClient, "/graphql_async/", True),
            "sync_no_optimizer": (Client, "/graphql/", False),
            "async_no_optimizer": (AsyncClient, "/graphql_async/", False),
        },
    )[request.param]

    optimizer_ctx = contextlib.nullcontext if with_optimizer else DjangoOptimizerExtension.disabled

    with optimizer_ctx(), GraphQLTestClient(path, client_class()) as c:
        yield c
