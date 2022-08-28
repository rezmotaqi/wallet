"""
middleware for x-process-time
"""
import time

from fastapi import Request


class ProcessTime:
    """
    Middleware to add a header x-process-time to return the time
    it took to process the request on server side.
    """
    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
