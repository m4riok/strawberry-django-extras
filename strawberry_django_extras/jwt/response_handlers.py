"""Response handlers for JWT authentication failures.

This module provides customizable response handlers for unauthorized access attempts.
Users can configure which handler to use via the JWT_UNAUTHORIZED_RESPONSE_HANDLER setting.
"""

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse

from strawberry_django_extras.jwt.exceptions import JSONWebTokenExpired

TOKEN_EXPIRED_ERROR_MESSAGE = "Token expired"
INVALID_TOKEN_ERROR_MESSAGE = "Invalid token"


def _get_error_message(exception: Exception) -> str:
    """Get the error message based on the exception type."""
    if isinstance(exception, JSONWebTokenExpired):
        return TOKEN_EXPIRED_ERROR_MESSAGE
    return INVALID_TOKEN_ERROR_MESSAGE


def json_response_handler(
    request: HttpRequest,
    exception: Exception,
    **kwargs: Any,
) -> JsonResponse:
    """Return a JSON response with error details.

    Args:
        request: The Django request object
        exception: The exception that caused the unauthorized response
        **kwargs: Additional context that can be used by custom handlers

    Returns:
        JsonResponse with 401 status code and error details
    """
    message = _get_error_message(exception)
    error = {
        "message": message,
        "code": "unauthorized",
        "hint": "Either use Valid Token or make requests without token.",
    }
    return JsonResponse({"errors": [error]}, status=401)


def http_response_handler(
    request: HttpRequest,
    exception: Exception,
    **kwargs: Any,
) -> HttpResponse:
    """Return a plain HTTP response with error message.

    Args:
        request: The Django request object
        exception: The exception that caused the unauthorized response
        **kwargs: Additional context that can be used by custom handlers

    Returns:
        HttpResponse with 401 status code and plain text error
    """
    message = _get_error_message(exception)
    return HttpResponse(message, status=401, content_type="text/plain")
