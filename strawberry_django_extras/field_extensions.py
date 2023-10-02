from __future__ import annotations

from typing import Callable, Any, Awaitable

from asgiref.sync import sync_to_async
from strawberry.extensions import FieldExtension
from strawberry.types import Info
from strawberry_django.fields.base import StrawberryDjangoFieldBase
from strawberry_django.fields.field import StrawberryDjangoField
from strawberry_django.optimizer import DjangoOptimizerExtension

from .decorators import sync_or_async
from .functions import rabbit_hole, kill_a_rabbit, perform_validation, check_permissions
from .inputs import CRUDInput


class MutationHooks(FieldExtension):

    def __init__(self, pre: Callable = None, post: Callable = None, pre_async: Callable = None,
                 post_async: Callable = None):
        self.pre = pre
        self.post = post
        self.pre_async = pre_async
        self.post_async = post_async

    def resolve(self, next_, source, info, **kwargs):
        if self.pre:
            self.pre(info, kwargs.get('data', None))

        result = next_(source, info, **kwargs)

        if self.post:
            self.post(info, kwargs.get('data', None), result)
        return result

    async def resolve_async(
            self, next_: Callable[..., Awaitable[Any]], source: Any, info: Info, **kwargs: Any
    ) -> Any:

        if self.pre_async:
            await self.pre_async(info, kwargs.get('data', None))
        else:
            if self.pre:
                await sync_or_async(self.pre)(info, kwargs.get('data', None))

        result = await next_(source, info, **kwargs)

        if self.post_async:
            await self.post_async(info, kwargs.get('data', None), result)
        else:
            if self.post:
                await sync_or_async(self.post)(info, kwargs.get('data', None), result)

        return result


class Validators(FieldExtension):
    def __init__(
            self,
            **kwargs,
    ):
        super().__init__(**kwargs)

    def resolve(self, next_, source, info, **kwargs):
        mutation_input = kwargs.get('data', None)
        perform_validation(mutation_input, info)
        return next_(source, info, **kwargs)

    async def resolve_async(
            self, next_: Callable[..., Awaitable[Any]], source: Any, info: Info, **kwargs: Any
    ) -> Any:
        mutation_input = kwargs.get('data', None)
        await sync_to_async(perform_validation)(mutation_input, info)
        return await next_(source, info, **kwargs)


class Permissions(FieldExtension):
    def __init__(
            self,
            **kwargs,
    ):
        super().__init__(**kwargs)

    def resolve(self, next_, source, info, **kwargs):
        mutation_input = kwargs.get('data', None)
        check_permissions(mutation_input, info)
        return next_(source, info, **kwargs)

    async def resolve_async(
            self, next_: Callable[..., Awaitable[Any]], source: Any, info: Info, **kwargs: Any
    ) -> Any:
        mutation_input = kwargs.get('data', None)
        await sync_to_async(check_permissions)(mutation_input, info)
        return await next_(source, info, **kwargs)


class Relationships(FieldExtension):
    root_field: StrawberryDjangoFieldBase = None

    def __init__(
            self,
            **kwargs,
    ):
        super().__init__(**kwargs)

    def apply(self, field: StrawberryDjangoField) -> None:
        self.root_field = field

    def resolve(self, next_, source, info, **kwargs):

        mutation_input = kwargs.get('data', None)
        model = self.root_field.django_model
        rel = {}
        rabbit_hole(model, mutation_input, rel)
        for k, v in mutation_input.__dict__.copy().items():
            if isinstance(v, CRUDInput):
                delattr(mutation_input, k)

        with DjangoOptimizerExtension.disabled():
            result = kill_a_rabbit(rel, None, False, is_root=True, next_=next_, source=source, info=info,
                                   ni=mutation_input)

        return result

    async def resolve_async(
            self, next_: Callable[..., Awaitable[Any]], source: Any, info: Info, **kwargs: Any
    ) -> Any:

        mutation_input = kwargs.get('data', None)
        model = self.root_field.django_model
        rel = {}
        await sync_to_async(rabbit_hole)(model, mutation_input, rel, None)
        for k, v in mutation_input.__dict__.copy().items():
            if isinstance(v, CRUDInput):
                delattr(mutation_input, k)

        with await sync_to_async(DjangoOptimizerExtension.disabled)():
            result = await sync_to_async(kill_a_rabbit)(rel, None, False, is_root=True, next_=next_, source=source,
                                                        info=info, ni=mutation_input)

        return result
