from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

import strawberry_django
from asgiref.sync import sync_to_async
from strawberry.extensions import FieldExtension
from strawberry_django.optimizer import DjangoOptimizerExtension

from .decorators import sync_or_async
from .functions import check_permissions, kill_a_rabbit, perform_validation, rabbit_hole
from .inputs import CRUDInput
from .types import PaginatedList

if TYPE_CHECKING:
    from strawberry.types import Info
    from strawberry_django.fields.base import StrawberryDjangoFieldBase
    from strawberry_django.fields.field import StrawberryDjangoField


# noinspection PyUnresolvedReferences
class MutationHooks(FieldExtension):
    # noinspection PyUnresolvedReferences
    def __init__(
        self,
        pre: Callable | None = None,
        post: Callable | None = None,
        pre_async: Callable | None = None,
        post_async: Callable | None = None,
    ):
        self.pre = pre
        self.post = post
        self.pre_async = pre_async
        self.post_async = post_async

    # wrapping required because somehow strawberry lands us in resolve instead of resolve_async even when
    # running in async context ( unless we have permission_classes which is weird, right? )
    @sync_or_async
    def resolve(self, next_, source, info, **kwargs):
        if self.pre:
            self.pre(info, kwargs.get("data", None))

        result = next_(source, info, **kwargs)

        if self.post:
            self.post(info, kwargs.get("data", None), result)
        return result

    async def resolve_async(
        self,
        next_: Callable[..., Awaitable[Any]],
        source: Any,
        info: Info,
        **kwargs: Any,
    ) -> Any:
        if self.pre_async:
            await self.pre_async(info, kwargs.get("data", None))
        elif self.pre:
            await sync_or_async(self.pre)(info, kwargs.get("data", None))

        result = await next_(source, info, **kwargs)

        if self.post_async:
            await self.post_async(info, kwargs.get("data", None), result)
        elif self.post:
            await sync_or_async(self.post)(info, kwargs.get("data", None), result)

        return result


class Validators(FieldExtension):
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)

    # wrapping required because somehow strawberry lands us in resolve instead of resolve_async even when
    # running in async context ( unless we have permission_classes which is weird, right? )
    @sync_or_async
    def resolve(self, next_, source, info, **kwargs):
        mutation_input = kwargs.get("data", None)
        perform_validation(mutation_input, info)
        return next_(source, info, **kwargs)

    async def resolve_async(
        self,
        next_: Callable[..., Awaitable[Any]],
        source: Any,
        info: Info,
        **kwargs: Any,
    ) -> Any:
        mutation_input = kwargs.get("data", None)
        await sync_to_async(perform_validation)(mutation_input, info)
        return await next_(source, info, **kwargs)


class Permissions(FieldExtension):
    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)

    # wrapping required because somehow strawberry lands us in resolve instead of resolve_async even when
    # running in async context ( unless we have permission_classes which is weird, right? )
    @sync_or_async
    def resolve(self, next_, source, info, **kwargs):
        mutation_input = kwargs.get("data", None)
        check_permissions(mutation_input, info)
        return next_(source, info, **kwargs)

    async def resolve_async(
        self,
        next_: Callable[..., Awaitable[Any]],
        source: Any,
        info: Info,
        **kwargs: Any,
    ) -> Any:
        mutation_input = kwargs.get("data", None)
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

    # wrapping required because somehow strawberry lands us in resolve instead of resolve_async even when
    # running in async context ( unless we have permission_classes which is weird, right? )
    @sync_or_async
    def resolve(self, next_, source, info, **kwargs):
        mutation_input = kwargs.get("data", None)
        model = self.root_field.django_model
        rel = {}
        rabbit_hole(model, mutation_input, rel)
        for k, v in mutation_input.__dict__.copy().items():
            if isinstance(v, CRUDInput):
                delattr(mutation_input, k)

        with DjangoOptimizerExtension.disabled():
            return kill_a_rabbit(
                rel,
                None,
                False,
                is_root=True,
                next_=next_,
                source=source,
                info=info,
                ni=mutation_input,
            )

    async def resolve_async(
        self,
        next_: Callable[..., Awaitable[Any]],
        source: Any,
        info: Info,
        **kwargs: Any,
    ) -> Any:
        mutation_input = kwargs.get("data", None)
        model = self.root_field.django_model
        rel = {}
        await sync_to_async(rabbit_hole)(model, mutation_input, rel, None)
        for k, v in mutation_input.__dict__.copy().items():
            if isinstance(v, CRUDInput):
                delattr(mutation_input, k)

        with await sync_to_async(DjangoOptimizerExtension.disabled)():
            return await sync_to_async(kill_a_rabbit)(
                rel,
                None,
                False,
                is_root=True,
                next_=next_,
                source=source,
                info=info,
                ni=mutation_input,
            )


# noinspection PyPropertyAccess
class TotalCountPaginationExtension(FieldExtension):
    django_model = None

    def apply(self, field: StrawberryDjangoField) -> None:
        # Resolve these now before changing the type
        field.is_list = field.is_list
        field.django_model = field.django_model
        field.django_type = field.django_type

        self.django_model = field.django_model

        # Now change the type
        field.type = PaginatedList[field.type]

    @sync_or_async
    def get_total_count(self, info: Info, filters=None) -> int:
        if filters is not None:
            return strawberry_django.filters.apply(
                filters,
                self.django_model.objects.all(),
                info,
            ).count()
        return self.django_model.objects.count()

    def resolve(self, next_, source, info, **kwargs):
        result = next_(source, info, **kwargs)
        return PaginatedList(
            results=result,
            total_count=self.get_total_count(
                filters=kwargs.get("filters", None),
                info=info,
            ),
        )

    async def resolve_async(
        self,
        next_: Callable[..., Awaitable[Any]],
        source: Any,
        info: Info,
        **kwargs: Any,
    ) -> Any:
        result = await next_(source, info, **kwargs)
        return PaginatedList(
            results=result,
            total_count=self.get_total_count(
                filters=kwargs.get("filters", None),
                info=info,
            ),
        )
