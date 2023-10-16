from typing import Generic, TypeVar

import strawberry

T = TypeVar("T")


@strawberry.type
class PaginatedList(Generic[T]):
    results: T
    total_count: int | None = None
