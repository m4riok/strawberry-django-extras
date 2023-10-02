from .decorators import sync_or_async
from .field_extensions import MutationHooks, Validators, Relationships, Permissions
from .inputs import CRUDInput, CRUDManyToOneCreateInput, CRUDManyToOneUpdateInput, CRUDOneToManyCreateInput, \
    CRUDOneToManyUpdateInput, CRUDManyToManyCreateInput, CRUDManyToManyUpdateInput, CRUDOneToOneCreateInput, \
    CRUDOneToOneUpdateInput

__all__ = [
    'sync_or_async',
    'JWTMutations',
    'mutation_hooks',
    'with_validation',
    'with_cud_relationships',
    'with_permissions',
    'CRUDInput',
    'CRUDManyToOneCreateInput',
    'CRUDManyToOneUpdateInput',
    'CRUDOneToManyCreateInput',
    'CRUDOneToManyUpdateInput',
    'CRUDManyToManyCreateInput',
    'CRUDManyToManyUpdateInput',
    'CRUDOneToOneCreateInput',
    'CRUDOneToOneUpdateInput',
]

from .jwt.mutations import JWTMutations


def mutation_hooks(pre: callable = None, post: callable = None, pre_async: callable = None,
                   post_async: callable = None):
    return MutationHooks(pre, post, pre_async, post_async)


def with_validation():
    return Validators()


def with_permissions():
    return Permissions()


def with_cud_relationships():
    return Relationships()
