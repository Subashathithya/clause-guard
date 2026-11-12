"""Safe error responses for the API.

Internal failures must never leak implementation details — stack traces, file
paths, upstream error text — to the person using the app. The real cause is
logged server-side together with a short reference the user can quote when they
report a problem.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException

logger = logging.getLogger("clauseguard.errors")


def public_error(
    status_code: int,
    message: str,
    exc: Exception | None = None,
) -> HTTPException:
    """Build an HTTPException with a safe message and a reference id.

    ``message`` must be written for the end user: it says what went wrong in
    plain language, never how the code broke.
    """
    reference = uuid.uuid4().hex[:10]
    if exc is not None:
        logger.exception("Request failed [%s]: %s", reference, message)
    else:
        logger.error("Request failed [%s]: %s", reference, message)
    return HTTPException(status_code=status_code, detail=f"{message} (reference {reference})")
