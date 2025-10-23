from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import jwt
import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from strawberry_django_extras.jwt.middleware import (
    INVALID_TOKEN_ERROR_MESSAGE,
    TOKEN_EXPIRED_ERROR_MESSAGE,
)
from strawberry_django_extras.jwt.settings import jwt_settings
from strawberry_django_extras.jwt.shortcuts import get_token
from strawberry_django_extras.jwt.utils import jwt_encode

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from pytest_django.fixtures import SettingsWrapper

    from tests.utils import GraphQLTestClient


User = get_user_model()


# GraphQL Query Constants
ME_QUERY_ALL_FIELDS = """
    query {
        me {
            username
            email
            isActive
            isSuperuser
            isStaff
        }
    }
"""


@pytest.mark.django_db(transaction=True)
def test_valid_token_returns_user_via_graphql_me_query(
    gql_client: GraphQLTestClient, valid_token: str, user: AbstractUser
) -> None:
    """Test that a valid JWT token authenticates user via GraphQL me query."""
    response = gql_client.query(
        ME_QUERY_ALL_FIELDS,
        headers={"Authorization": f"JWT {valid_token}"},
    )

    assert response.data is not None
    assert response.data["me"] is not None
    assert response.data["me"]["username"] == user.username
    assert response.data["me"]["email"] == user.email
    assert response.data["me"]["isActive"] is True


@pytest.mark.django_db(transaction=True)
@override_settings(
    GRAPHQL_JWT={
        "JWT_AUDIENCE": "test-audience",
        "JWT_ISSUER": "test-issuer",
    }
)
def test_valid_token_with_audience_and_issuer(
    gql_client: GraphQLTestClient, user: Any
) -> None:
    """Test that JWT with audience and issuer works via GraphQL."""
    jwt_settings.reload()
    token = get_token(user)

    response = gql_client.query(
        ME_QUERY_ALL_FIELDS,
        headers={"Authorization": f"JWT {token}"},
    )

    assert response.data is not None
    assert response.data["me"] is not None
    assert response.data["me"]["username"] == user.username


@pytest.mark.django_db(transaction=True)
def test_token_with_invalid_signature_returns_error(
    gql_client: GraphQLTestClient, user: Any
) -> None:
    """Test that a JWT token with invalid signature returns error."""
    # Create a token with a different secret key
    payload = {
        User.USERNAME_FIELD: user.get_username(),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    invalid_token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

    response = gql_client.query(
        ME_QUERY_ALL_FIELDS,
        headers={"Authorization": f"JWT {invalid_token}"},
        assert_no_errors=False,
    )

    assert response.errors is not None
    assert len(response.errors) == 1
    assert response.errors[0]["message"] == INVALID_TOKEN_ERROR_MESSAGE


@pytest.mark.django_db(transaction=True)
def test_no_authorization_header_returns_null(gql_client: GraphQLTestClient) -> None:
    """Test that missing authorization header returns null for me query."""
    response = gql_client.query(ME_QUERY_ALL_FIELDS)

    assert response.data["me"] is None


@pytest.mark.django_db(transaction=True)
def test_token_for_nonexistent_user_returns_null(gql_client: GraphQLTestClient) -> None:
    """Test that a JWT token for a non-existent user returns null."""
    # Create a token for a user that doesn't exist
    payload = {
        User.USERNAME_FIELD: "nonexistent_user_12345",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt_encode(payload)

    response = gql_client.query(
        ME_QUERY_ALL_FIELDS,
        headers={"Authorization": f"JWT {token}"},
        assert_no_errors=False,
    )

    assert response.data["me"] is None


@pytest.mark.django_db(transaction=True)
def test_token_for_inactive_user_returns_error(
    gql_client: GraphQLTestClient, user: Any
) -> None:
    """Test that a JWT token for an inactive user returns an error."""
    token = get_token(user)
    user.is_active = False
    user.save()

    response = gql_client.query(
        ME_QUERY_ALL_FIELDS,
        headers={"Authorization": f"JWT {token}"},
        assert_no_errors=False,
    )

    assert response.errors is not None
    assert len(response.errors) == 1
    assert response.errors[0]["message"] == INVALID_TOKEN_ERROR_MESSAGE


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "invalid_token",
    [
        "",
        "not-a-token",
        "invalid",
        "a.b",  # Too few segments
        "this.is.not.a.valid.token",
    ],
)
def test_completely_invalid_token_format(
    gql_client: GraphQLTestClient, invalid_token: str
) -> None:
    """Test that completely invalid token formats return an error."""
    # Empty token should not trigger an error (it's like no auth header)
    if invalid_token == "":
        response = gql_client.query(ME_QUERY_ALL_FIELDS)
        assert response.data["me"] is None
    else:
        response = gql_client.query(
            ME_QUERY_ALL_FIELDS,
            headers={"Authorization": f"JWT {invalid_token}"},
            assert_no_errors=False,
        )
        assert response.errors is not None
        assert len(response.errors) == 1
        assert response.errors[0]["message"] == INVALID_TOKEN_ERROR_MESSAGE


@pytest.mark.django_db(transaction=True)
@override_settings(
    GRAPHQL_JWT={
        "JWT_VERIFY_EXPIRATION": True,
        "JWT_EXPIRATION_DELTA": timedelta(seconds=-1),  # Already expired
    }
)
def test_expired_token_returns_error(gql_client: GraphQLTestClient, user: Any) -> None:
    """Test that an expired JWT token returns an error."""
    jwt_settings.reload()

    # Create a token that's already expired
    token = get_token(user)

    response = gql_client.query(
        ME_QUERY_ALL_FIELDS,
        headers={"Authorization": f"JWT {token}"},
        assert_no_errors=False,
    )

    assert response.errors is not None
    assert len(response.errors) == 1
    assert response.errors[0]["message"] == TOKEN_EXPIRED_ERROR_MESSAGE


@pytest.mark.parametrize("verify_expiration", [False, True])
@pytest.mark.django_db(transaction=True)
def test_expired_token_accepted_when_verification_disabled(
    gql_client: GraphQLTestClient,
    user: AbstractUser,
    settings: SettingsWrapper,
    verify_expiration: bool,
) -> None:
    """Test that expired tokens work when expiration verification is disabled."""
    settings.GRAPHQL_JWT["JWT_VERIFY_EXPIRATION"] = verify_expiration
    jwt_settings.reload()
    payload = {
        User.USERNAME_FIELD: user.get_username(),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt_encode(payload)

    response = gql_client.query(
        ME_QUERY_ALL_FIELDS,
        headers={"Authorization": f"JWT {expired_token}"},
        assert_no_errors=False,
    )

    if verify_expiration:
        # Should return error when verification is enabled
        assert response.errors is not None
        assert len(response.errors) == 1
        assert response.errors[0]["message"] == TOKEN_EXPIRED_ERROR_MESSAGE
    else:
        # Should work when verification is disabled
        assert response.data is not None
        assert response.data["me"] is not None
        assert response.data["me"]["username"] == user.username
