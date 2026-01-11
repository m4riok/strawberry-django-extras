from graphql.validation import NoSchemaIntrospectionCustomRule
from strawberry.extensions import SchemaExtension

from strawberry_django_extras.jwt.decorators import sync_or_async
from strawberry_django_extras.jwt.settings import jwt_settings


class DisableAnonymousIntrospection(SchemaExtension):
    @sync_or_async
    def on_validation_start(self) -> None:
        schema_context = self.execution_context.context
        request = schema_context.request

        if not request.user.is_authenticated and jwt_settings.JWT_AUTHENTICATE_INTROSPECTION:
            self.execution_context.validation_rules = (
                *self.execution_context.validation_rules,
                NoSchemaIntrospectionCustomRule,
            )
