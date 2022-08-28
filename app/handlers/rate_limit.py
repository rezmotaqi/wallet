"""The rate_limit utils."""

from fastapi import Response, Request, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Build a simple JSON response that includes the details of the rate limit
    that was hit. If no limit is hit, the countdown is added to headers.
    """
    response = Response(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=f"Rate limit exceeded: {exc.detail}"
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response


limiter = Limiter(key_func=get_remote_address)
