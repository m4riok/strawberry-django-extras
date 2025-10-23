from django.urls import path
from strawberry.django.views import AsyncGraphQLView, GraphQLView

from tests.schema import schema

urlpatterns = [
    path("graphql/", GraphQLView.as_view(schema=schema)),
    path("graphql_async/", AsyncGraphQLView.as_view(schema=schema)),
]
