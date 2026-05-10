class DomainError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    default_message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"
    default_message = "Resource not found"


class UnauthorizedError(DomainError):
    status_code = 401
    code = "unauthorized"
    default_message = "Authentication required"


class ForbiddenError(DomainError):
    status_code = 403
    code = "forbidden"
    default_message = "Access denied"


class BadRequestError(DomainError):
    status_code = 400
    code = "bad_request"
    default_message = "Invalid request"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"
    default_message = "Resource conflict"


class ExternalServiceError(DomainError):
    status_code = 502
    code = "external_service_error"
    default_message = "External service unavailable"
