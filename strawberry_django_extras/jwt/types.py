from typing import Optional

import strawberry
from strawberry import UNSET


@strawberry.type
class RefreshTokenType:
    token: str
    exp: int
    iat: int


@strawberry.type
class TokenType:
    token: str
    refresh_token: Optional[RefreshTokenType] = UNSET


@strawberry.type
class TokenPayloadType:
    exp: int
    iat: int
