class AppError(Exception):
    """Error that can be shown to the client. `internal` is for server logs only."""

    status_code = 400

    def __init__(self, message: str, *, code: str = "error", internal: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.internal = internal


class InputRejected(AppError):
    status_code = 400

    def __init__(self, message: str, *, code: str = "invalid_input", internal: str = "") -> None:
        super().__init__(message, code=code, internal=internal)


class AuthError(AppError):
    status_code = 401

    def __init__(self, message: str = "Authentication is required.", *, code: str = "unauthenticated") -> None:
        super().__init__(message, code=code)


class PermissionDenied(AppError):
    status_code = 403

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message, code="forbidden")


class NotFoundError(AppError):
    status_code = 404

    def __init__(self, message: str = "The requested record was not found.") -> None:
        super().__init__(message, code="not_found")


class ConflictError(AppError):
    status_code = 409

    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict")


class RateLimitError(AppError):
    status_code = 429

    def __init__(self, message: str = "Too many requests. Wait a moment and try again.") -> None:
        super().__init__(message, code="rate_limited")


class InfrastructureError(AppError):
    status_code = 503

    def __init__(self, message: str, *, internal: str = "") -> None:
        super().__init__(message, code="infrastructure", internal=internal)
