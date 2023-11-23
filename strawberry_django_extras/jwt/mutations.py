from typing import Optional

import strawberry
from django.contrib.auth import authenticate, get_user_model
from makefun import with_signature
from strawberry import UNSET
from strawberry.types import Info

from strawberry_django_extras.exceptions import JWTError

from .decorators import sync_or_async
from .settings import jwt_settings
from .shortcuts import get_token, get_user_by_token
from .types import RefreshTokenType, TokenPayloadType, TokenType
from .utils import get_payload

if jwt_settings.JWT_LONG_RUNNING_REFRESH_TOKEN:
    from .refresh_token.shortcuts import (
        create_refresh_token,
        get_refresh_token,
        get_refresh_token_user,
    )

# including these so auto import cleanup doesn't remove them
k_junk = Optional[str]
l_junk = UNSET
i_junk = Info


# noinspection PyUnusedLocal
class JWTMutations:
    @strawberry.mutation
    @sync_or_async
    @with_signature(
        "issue(self, info: Info, %s: Optional[str] = UNSET, password: Optional[str] = UNSET, refresh_token: Optional[str] = UNSET) -> TokenType"
        % get_user_model().USERNAME_FIELD
    )
    def issue(self, **kwargs) -> TokenType:  # noqa: PLR0912
        refresh_token = None

        r_token = kwargs.get("refresh_token", UNSET)
        uname_field = kwargs.get(get_user_model().USERNAME_FIELD, UNSET)
        password = kwargs.get("password", UNSET)

        if r_token is UNSET and (uname_field is UNSET or password is UNSET):
            raise JWTError("Invalid arguments")

        # try to authenticate the user using the provided credentials.
        if r_token is not UNSET:
            if not jwt_settings.JWT_ALLOW_REFRESH:
                raise JWTError("Token refresh not supported")

            if jwt_settings.JWT_LONG_RUNNING_REFRESH_TOKEN:
                old_refresh_token = get_refresh_token(r_token, None)
                if old_refresh_token.is_expired():
                    raise JWTError("Token expired")
                user = get_refresh_token_user(old_refresh_token)
                token = get_token(user)
                # choose whether we provide a new refresh token on each request or not

                if jwt_settings.JWT_REUSE_REFRESH_TOKENS:
                    new_refresh_token = create_refresh_token(user, old_refresh_token)
                    refresh_token = RefreshTokenType(
                        token=new_refresh_token.token,
                        exp=new_refresh_token.get_exp(),
                        iat=new_refresh_token.get_iat(),
                    )
                else:
                    refresh_token = RefreshTokenType(
                        token=old_refresh_token.token,
                        exp=old_refresh_token.get_exp(),
                        iat=old_refresh_token.get_iat(),
                    )
            else:
                try:
                    user = get_user_by_token(r_token)
                except Exception as e:  # noqa: BLE001
                    raise JWTError("Token expired") from e

                token = get_token(user)
        else:
            creds = {get_user_model().USERNAME_FIELD: uname_field, "password": password}
            try:
                user = authenticate(**creds)
            except Exception as e:  # noqa: BLE001
                raise JWTError("Authentication failure") from e

            if user is None:
                raise JWTError("Authentication failure")

            token = get_token(user)

            if jwt_settings.JWT_ALLOW_REFRESH and jwt_settings.JWT_LONG_RUNNING_REFRESH_TOKEN:
                new_refresh_token = create_refresh_token(user, None)
                refresh_token = RefreshTokenType(
                    token=new_refresh_token.token,
                    exp=new_refresh_token.get_exp(),
                    iat=new_refresh_token.get_iat(),
                )

        return TokenType(token=token, refresh_token=refresh_token)

    # noinspection PyUnusedLocal
    @strawberry.mutation
    @sync_or_async
    def revoke(self, info: Info, token: str) -> bool:
        refresh_token = get_refresh_token(token, None)
        refresh_token.revoke()
        return True

    @strawberry.mutation
    @sync_or_async
    def verify(self, info: Info, token: str) -> TokenPayloadType:
        payload = get_payload(token)
        return TokenPayloadType(exp=payload["exp"], iat=payload["origIat"])
