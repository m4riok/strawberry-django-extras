# JWT Authentication

For installation and basic configuration instructions please refer to the [quick start guide](../quickstart.md).

## Settings

Settings can be configured by defining the `GRAPHQL_JWT` dictionary in your Django settings.

```python
GRAPHQL_JWT = {
    'JWT_ALGORITHM': 'EdDSA',
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LONG_RUNNING_REFRESH_TOKEN': True,
    'JWT_EXPIRATION_DELTA': datetime.timedelta(minutes=5),
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_AUTHENTICATE_INTROSPECTION': True,
    'JWT_REFRESH_TOKEN_N_BYTES': 64,
    'JWT_PRIVATE_KEY': base64.b64decode('YOUR_PRIVATE_KEY'),
    'JWT_PUBLIC_KEY': base64.b64decode('YOUR_PUBLIC_KEY')
}
```
<br />

The following settings are available for this module:

### JWT_ALGORITHM
Algorithm used to sign the JWT. Defaults to `HS256`.

### JWT_AUDIENCE¶
Audience claim (aud) to be included in the JWT. Defaults to `None`.

### JWT_ISSUER
Issuer claim (iss) to be included in the JWT. Defaults to `None`.

### JWT_LEEWAY
Leeway time for JWT expiration verification. Defaults to `0`.

### JWT_SECRET_KEY
Secret key used to sign the JWT. Defaults to `settings.SECRET_KEY`.

### JWT_PUBLIC_KEY
Public key used to verify the JWT. Defaults to `None`.

> This assumes you are using asymmetric cryptography so `JWT_SECRET_KEY` is not used and `JWT_ALGORITH` must be set accordingly.

### JWT_PRIVATE_KEY
Private key used to verify the JWT. Defaults to `None`.

> This assumes you are using asymmetric cryptography so `JWT_SECRET_KEY` is not used and `JWT_ALGORITH` must be set accordingly.

### JWT_VERIFY
Secret key verification. Defaults to `True`.

### JWT_ENCODE_HANDLER
Function used to encode the JWT.

### JWT_DECODE_HANDLER
Function used to decode the JWT.

### JWT_PAYLOAD_HANDLER
Function used to generate the JWT payload.

### JWT_PAYLOAD_GET_USERNAME_HANDLER
Function used to get the username from the user model. 
```python
lambda payload: payload.get(get_user_model().USERNAME_FIELD)
```

### JWT_GET_USER_BY_NATURAL_KEY_HANDLER
Function used to get the user by its natural key. 
```python
get_user_by_natural_key(username)
```

### JWT_VERIFY_EXPIRATION
Expiration time verification. Defaults to `False`.

### JWT_EXPIRATION_DELTA
Expiration delta added to `utcnow()` to determine token expiration. Defaults to `datetime.timedelta(seconds=300)`.

### JWT_ALLOW_REFRESH
Enables token refresh. Defaults to `True`.
> If used together with `JWT_LONG_RUNNING_REFRESH_TOKEN` this will allow the user to refresh the token using the refresh token. Otherwise, the user will have to use his JWT token prior to expiration to get a new one.

### JWT_REFRESH_EXPIRATION_DELTA
Timedelta used for refresh token expiration. Defaults to `datetime.timedelta(days=7)`.

### JWT_LONG_RUNNING_REFRESH_TOKEN
Enables long-running refresh tokens. Defaults to `False`.

### JWT_REFRESH_TOKEN_MODEL
Model used for refresh tokens.

### JWT_REFRESH_TOKEN_N_BYTES
Long-running refresh token number of bytes. Defaults to `20`.

### JWT_REUSE_REFRESH_TOKENS
A new long-running refresh token is being generated but replaces the existing database record and thus invalidates the previous long running refresh token. Defaults to `False`.

### JWT_REFRESH_EXPIRED_HANDLER
Function used to handle expired refresh tokens.

### JWT_GET_REFRESH_TOKEN_HANDLER
A custom function to retrieve a long time refresh token instance.

### JWT_AUTH_HEADER_NAME
Name of the HTTP header used for authentication. Defaults to `HTTP_AUTHORIZATION`.

### JWT_AUTH_HEADER_PREFIX
Prefix for the HTTP header used for authentication. Defaults to `JWT`.

### JWT_AUTHENTICATE_INTROSPECTION
Limits introspection to authenticated users. Defaults to `False`.

### JWT_UNAUTHORIZED_RESPONSE_HANDLER
Function used to handle unauthorized JWT authentication failures. This allows customization of the response format returned when JWT authentication fails (e.g., invalid token, expired token).

The handler should accept the following parameters:
- `request` (HttpRequest): The Django request object that triggered the authentication failure
- `exception` (Exception): The exception instance that was raised (e.g., `JSONWebTokenExpired`, `JSONWebTokenError`)

The handler determines the error message based on the exception type. Use `isinstance(exception, JSONWebTokenExpired)` to distinguish between expired and invalid tokens.

**Available built-in handlers:**

- `strawberry_django_extras.jwt.response_handlers.json_response_handler` - Returns a structured JSON response with error details (default)
- `strawberry_django_extras.jwt.response_handlers.http_response_handler` - Returns a plain text HTTP response

**Example:**

```python
GRAPHQL_JWT = {
    'JWT_UNAUTHORIZED_RESPONSE_HANDLER': 'strawberry_django_extras.jwt.response_handlers.json_response_handler',
}
```

**Custom handler example:**

```python
from django.http import HttpRequest, JsonResponse
from strawberry_django_extras.jwt.exceptions import JSONWebTokenExpired

def custom_response_handler(
    request: HttpRequest,
    exception: Exception,
    **kwargs
) -> JsonResponse:
    # Determine message based on exception type
    if isinstance(exception, JSONWebTokenExpired):
        message = "Your session has expired. Please log in again."
    else:
        message = "Authentication failed. Please check your credentials."

    # Build response with request context
    response_data = {
        'error': message,
        'status': 'unauthorized',
        'path': request.path,
        'exception_type': exception.__class__.__name__,
    }

    return JsonResponse(response_data, status=401)

# In settings:
GRAPHQL_JWT = {
    'JWT_UNAUTHORIZED_RESPONSE_HANDLER': 'myapp.handlers.custom_response_handler',
}
```