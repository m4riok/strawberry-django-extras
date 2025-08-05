# Lazy Loading

This package provides context-aware lazy loading classes that solve async context detection problems by deferring schema building until the first request or WebSocket connection. This ensures that schema evaluation happens in the correct execution context.

## Available Exports

The `lazy` module provides two main classes:

- **`ContextAwareLazyView`** - For HTTP GraphQL endpoints
- **`ContextAwareLazyConsumer`** - For WebSocket GraphQL endpoints

Both classes defer parent class initialization until the first interaction, ensuring schema building happens when async context is guaranteed to be available.

## Critical Requirements

!!! warning "Schema Must Be Passed as String"
    
    Both lazy classes **MUST** receive the schema as a string module path (e.g., `"app.schema"`), **NOT** as a direct schema object. This is critical for preventing early schema evaluation.

    ```python    
    ContextAwareLazyView.as_view(schema="app.schema")
    ```

!!! note "Schema Import Isolation"
    
    For lazy loading to work properly, your schema should **NOT** be imported anywhere else in your codebase during Django startup. Strawberry evaluates schemas at import time, so any import will trigger early schema building and defeat the lazy loading mechanism.

## Performance Considerations

!!! info "First Request Latency"
    
    Since schema building is deferred until the first request/connection, expect some additional latency on the initial interaction. Subsequent requests will use the cached schema and perform normally.

## HTTP GraphQL Endpoints

Use `ContextAwareLazyView` for standard HTTP GraphQL endpoints:

```{.python title="urls.py"}
from django.urls import path
from strawberry_django_extras.lazy import ContextAwareLazyView

urlpatterns = [
    path("graphql/", ContextAwareLazyView.as_view(schema="app.schema")),
]
```

```{.python title="app/schema.py"}
import strawberry
from strawberry_django_extras.field_extensions import with_total_count

@strawberry.type
class Query:
    users: list[UserType] = strawberry_django.field(
        extensions=[with_total_count()]
    )

@strawberry.type 
class Mutation:
    # Your mutations here
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)
```

## WebSocket GraphQL Endpoints

Use `ContextAwareLazyConsumer` for GraphQL subscriptions over WebSocket:

```{.python title="asgi.py"}
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import re_path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django_asgi_app = get_asgi_application()

from strawberry_django_extras.lazy import ContextAwareLazyConsumer  # noqa: E402

gql_ws_consumer = ContextAwareLazyConsumer.as_asgi(schema="app.schema")

application = ProtocolTypeRouter({
    "http": URLRouter(
        [
            re_path("^", django_asgi_app),
        ],
    ),
    "websocket": URLRouter([
        re_path(r"graphql", gql_ws_consumer),
    ]),
})
```

```{.python title="app/schema.py"}
import strawberry
from strawberry_django_extras.field_extensions import mutation_hooks

@strawberry.type
class Query:
    # Your queries here
    pass

@strawberry.type
class Mutation:
    # Your mutations here  
    pass

@strawberry.type
class Subscription:
    # Your subscriptions here
    pass

schema = strawberry.Schema(
    query=Query, 
    mutation=Mutation, 
    subscription=Subscription
)
```


## When to Use Lazy Loading

Lazy loading is particularly beneficial when:

- Running Django tests with async GraphQL operations
- Experiencing async context detection issues
- Using field extensions that need to detect execution context
- Working in hybrid sync/async environments

!!! tip "Django Testing"
    
    Lazy loading is especially useful for Django testing scenarios where schemas are imported during URL resolution (sync context) but executed in async context via `async_to_sync()`.

