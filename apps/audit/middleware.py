import logging
import re
import time
import uuid

from core.request_context import request_id_var

logger = logging.getLogger("api.request")
SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        # Only accept simple IDs from clients, so nobody can inject junk into our logs.
        request_id = incoming if SAFE_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.monotonic()
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            user = getattr(request, "user", None)
            user_id = user.pk if user is not None and user.is_authenticated else "-"
            logger.info(
                "%s %s %s %.1fms user=%s",
                request.method, request.path, response.status_code,
                (time.monotonic() - started) * 1000, user_id,
            )
            return response
        finally:
            request_id_var.reset(token)