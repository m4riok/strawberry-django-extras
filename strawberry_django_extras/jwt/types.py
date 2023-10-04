from typing import Optional

import strawberry
from strawberry import UNSET


@strawberry.type
class RefreshedTokenType:
    token: str
    exp: int
    iat: int


@strawberry.type
class TokenType:
    token: str
    refresh_token: Optional[RefreshedTokenType] = UNSET


@strawberry.type
class TokenPayloadType:
    exp: int
    iat: int
