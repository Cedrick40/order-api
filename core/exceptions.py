import logging

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class AppError(APIException):
    """Base class for our own business errors (stock, status changes, etc.)."""
    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"
    default_detail = "We couldn't process that request."

    def __init__(self, message=None, details=None, code=None):
        self.message = message or self.default_detail
        self.details = details or {}
        if code:
            self.code = code
        super().__init__(detail=self.message)

class InsufficientStock(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "INSUFFICIENT_STOCK"
    default_detail = "Not enough stock available."


DEFAULT_MESSAGES = {
    401: ("NOT_AUTHENTICATED", "Please log in to continue. Your login may be incorrect or expired."),
    403: ("PERMISSION_DENIED", "Your account isn't allowed to do this."),
    404: ("NOT_FOUND", "We couldn't find what you were looking for."),
    405: ("METHOD_NOT_ALLOWED", "That action isn't supported on this address."),
    429: ("TOO_MANY_REQUESTS", "Too many attempts. Please wait a moment and try again."),
}


def _body(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _first_message(data):
    """Pull the first human-readable message out of DRF's nested error data."""
    if isinstance(data, dict):
        for field, value in data.items():
            msg = _first_message(value)
            if msg:
                return msg if field in ("non_field_errors", "detail") else f"{field}: {msg}"
    elif isinstance(data, (list, tuple)):
        for item in data:
            msg = _first_message(item)
            if msg:
                return msg
    elif data is not None:
        return str(data)
    return None


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    # Not an API error at all: a real bug. Log it, hide the details from the client.
    if response is None:
        logger.exception("Unhandled server error")
        return Response(
            _body("SERVER_ERROR", "Something went wrong on our side. Please try again."),
            status=500,
        )

    if isinstance(exc, AppError):
        response.data = _body(exc.code, exc.message, exc.details)
    elif isinstance(exc, ValidationError):
        message = _first_message(response.data) or "Some of the information you sent is not valid."
        response.data = _body("VALIDATION_ERROR", message, response.data)
    elif response.status_code in DEFAULT_MESSAGES:
        code, message = DEFAULT_MESSAGES[response.status_code]
        response.data = _body(code, message)
    else:
        response.data = _body("BAD_REQUEST", "We couldn't process that request.")
    return response

class DuplicateProduct(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "DUPLICATE_PRODUCT"


class ProductUnavailable(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "PRODUCT_UNAVAILABLE"


class InvalidStatusTransition(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_STATUS_TRANSITION"


class OrderNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    default_detail = "We couldn't find that order on your account."