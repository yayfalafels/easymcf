"""Error types shared by easymcf/api and easymcf/services."""

from __future__ import annotations


class ApiError(Exception):
    status = 400
    error = "validation_error"

    def __init__(self, message: str, field: str | None = None, **extra):
        super().__init__(message)
        self.message = message
        self.field = field
        self.extra = extra


class ValidationFailed(ApiError):
    status, error = 400, "validation_error"


class RecordNotFound(ApiError):
    status, error = 404, "not_found"


class Conflict(ApiError):
    status, error = 409, "conflict"
