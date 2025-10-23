import asyncio
import contextvars
import inspect
from typing import Any, cast

from django.test.client import AsyncClient, Client
from strawberry.test.client import Response
from strawberry_django.test.client import TestClient
from typing_extensions import override

_client: contextvars.ContextVar["GraphQLTestClient"] = contextvars.ContextVar(
    "_client_ctx",
)


class GraphQLTestClient(TestClient):
    """GraphQL test client for Django integration testing."""

    def __init__(
        self,
        path: str,
        client: Client | AsyncClient,
    ):
        super().__init__(path, client=cast("Client", client))
        self._token: contextvars.Token | None = None
        self.is_async = isinstance(client, AsyncClient)

    def __enter__(self):
        self._token = _client.set(self)
        return self

    def __exit__(self, *args, **kwargs):
        assert self._token
        _client.reset(self._token)

    def request(
        self,
        body: dict[str, object],
        headers: dict[str, object] | None = None,
        files: dict[str, object] | None = None,
    ):
        kwargs: dict[str, object] = {"data": body}
        if files:
            kwargs["format"] = "multipart"
        else:
            kwargs["content_type"] = "application/json"

        if headers:
            kwargs["headers"] = headers

        return self.client.post(
            self.path,
            **kwargs,
        )

    @override
    def query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        headers: dict[str, object] | None = None,
        files: dict[str, object] | None = None,
        assert_no_errors: bool | None = True,
    ) -> Response:
        body = self._build_body(query, variables, files)

        resp = self.request(body, headers, files)
        if inspect.iscoroutine(resp):
            resp = asyncio.run(resp)

        data = self._decode(resp, type="multipart" if files else "json")

        response = Response(
            errors=data.get("errors"),
            data=data.get("data"),
            extensions=data.get("extensions"),
        )

        if assert_no_errors:
            assert response.errors is None

        return response
