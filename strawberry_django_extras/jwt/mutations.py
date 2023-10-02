from typing import Optional

import strawberry
from django.contrib.auth import get_user_model, authenticate
from makefun import with_signature
from strawberry import UNSET
from strawberry.types import Info

from .decorators import sync_or_async
from .refresh_token.shortcuts import get_refresh_token, create_refresh_token, get_refresh_token_user
from .settings import jwt_settings
from .shortcuts import get_token, get_user_by_token
from .types import TokenType, RefreshedTokenType, TokenPayloadType
from .utils import get_payload

# including these so auto import cleanup doesn't remove them
k_junk = Optional[str]
l_junk = UNSET
i_junk = Info


class JWTMutations:
    @strawberry.mutation
    @sync_or_async
    @with_signature(
        'issue(self, info: Info, %s: Optional[str] = UNSET, password: Optional[str] = UNSET, refresh_token: Optional[str] = UNSET) -> TokenType' % get_user_model().USERNAME_FIELD)
    def issue(self, **kwargs) -> TokenType:

        token = None
        refresh_token = None

        r_token = kwargs.get('refresh_token', UNSET)
        uname_field = kwargs.get(get_user_model().USERNAME_FIELD, UNSET)
        password = kwargs.get('password', UNSET)

        if r_token is UNSET and (uname_field is UNSET or password is UNSET):
            raise Exception("Invalid arguments")

        # try to authenticate the user using the provided credentials.
        if r_token is not UNSET:
            if not jwt_settings.JWT_ALLOW_REFRESH:
                raise Exception("Token refresh not supported")

            if jwt_settings.JWT_LONG_RUNNING_REFRESH_TOKEN:
                old_refresh_token = get_refresh_token(r_token, None)
                if old_refresh_token.is_expired():
                    raise Exception("Token expired")
                user = get_refresh_token_user(old_refresh_token)
                token = get_token(user)
                # choose whether we provide a new refresh token on each request or not

                if jwt_settings.JWT_REUSE_REFRESH_TOKENS:
                    new_refresh_token = create_refresh_token(user, old_refresh_token)
                    refresh_token = RefreshedTokenType(
                        token=new_refresh_token.token,
                        exp=new_refresh_token.get_exp(),
                        iat=new_refresh_token.get_iat()
                    )
                else:
                    refresh_token = RefreshedTokenType(
                        token=old_refresh_token.token,
                        exp=old_refresh_token.get_exp(),
                        iat=old_refresh_token.get_iat()
                    )
            else:
                try:
                    user = get_user_by_token(r_token)
                except Exception:
                    raise Exception("Token expired")

                token = get_token(user)
        else:
            creds = {get_user_model().USERNAME_FIELD: uname_field, 'password': password}
            try:
                user = authenticate(**creds)
            except Exception:
                raise Exception("Authentication failure")
                # raise e

            if user is None:
                raise Exception("Authentication failure")

            token = get_token(user)

            if jwt_settings.JWT_ALLOW_REFRESH and jwt_settings.JWT_LONG_RUNNING_REFRESH_TOKEN:
                new_refresh_token = create_refresh_token(user, None)
                refresh_token = RefreshedTokenType(
                    token=new_refresh_token.token,
                    exp=new_refresh_token.get_exp(),
                    iat=new_refresh_token.get_iat()
                )

        return TokenType(token=token, refreshToken=refresh_token) if refresh_token else TokenType(token=token)

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
        return TokenPayloadType(exp=payload['exp'], iat=payload['origIat'])