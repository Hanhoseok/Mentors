import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.logging import request_id_var

from .base import BadRequestError, DomainError

logger = logging.getLogger("exception")


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    if exc.status_code >= 500:
        logger.error(
            "domain error",
            extra={"code": exc.code, "status_code": exc.status_code, "path": request.url.path},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": request_id_var.get(),
        },
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    err = BadRequestError("Validation failed")
    return JSONResponse(
        status_code=err.status_code,
        content={
            "code": err.code,
            "message": err.message,
            "request_id": request_id_var.get(),
            "details": exc.errors(),
        },
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": request_id_var.get(),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
