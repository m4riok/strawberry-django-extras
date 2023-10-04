from .decorators import sync_or_async
from .field_extensions import MutationHooks, Permissions, Relationships, Validators
from .inputs import (
    CRUDInput,
    CRUDManyToManyCreateInput,
    CRUDManyToManyUpdateInput,
    CRUDManyToOneCreateInput,
    CRUDManyToOneUpdateInput,
    CRUDOneToManyCreateInput,
    CRUDOneToManyUpdateInput,
    CRUDOneToOneCreateInput,
    CRUDOneToOneUpdateInput,
)

__all__ = [
    "sync_or_async",
    "JWTMutations",
    "mutation_hooks",
    "with_validation",
    "with_cud_relationships",
    "with_permissions",
    "CRUDInput",
    "CRUDManyToOneCreateInput",
    "CRUDManyToOneUpdateInput",
    "CRUDOneToManyCreateInput",
    "CRUDOneToManyUpdateInput",
    "CRUDManyToManyCreateInput",
    "CRUDManyToManyUpdateInput",
    "CRUDOneToOneCreateInput",
    "CRUDOneToOneUpdateInput",
]

from typing import Optional

from .jwt.mutations import JWTMutations


def mutation_hooks(
    pre: Optional[callable] = None,
    post: Optional[callable] = None,
    pre_async: Optional[callable] = None,
    post_async: Optional[callable] = None,
):
    return MutationHooks(pre, post, pre_async, post_async)


def with_validation():
    return Validators()


def with_permissions():
    return Permissions()


def with_cud_relationships():
    return Relationships()
