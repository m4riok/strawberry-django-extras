import importlib

from strawberry.channels import GraphQLWSConsumer
from strawberry.django.views import AsyncGraphQLView


class ContextAwareLazyView(AsyncGraphQLView):
    def __init__(self, **kwargs):
        self._init_kwargs = kwargs
        self.schema_str = kwargs.get("schema")
        self._is_initialized = False

    async def dispatch(self, request, *args, **kwargs):
        if not self._is_initialized:
            schema = importlib.import_module(self.schema_str)  # type: ignore  # noqa: PGH003
            self._init_kwargs["schema"] = schema.schema  # type: ignore  # noqa: PGH003

            super().__init__(**self._init_kwargs)
            self._is_initialized = True

        return await super().dispatch(request, *args, **kwargs)


class ContextAwareLazyConsumer(GraphQLWSConsumer):
    def __init__(self, **kwargs):
        self._init_kwargs = kwargs
        self.schema_str = kwargs.get("schema")
        self._is_initialized = False

    async def _ensure_initialized(self):
        if not self._is_initialized:
            schema = importlib.import_module(self.schema_str)  # type: ignore  # noqa: PGH003
            self._init_kwargs["schema"] = schema.schema  # type: ignore  # noqa: PGH003

            super().__init__(**self._init_kwargs)
            self._is_initialized = True

    async def connect(self):
        await self._ensure_initialized()

        return await super().connect()

    async def websocket_connect(self, message):
        await self._ensure_initialized()

        return await super().websocket_connect(message)
