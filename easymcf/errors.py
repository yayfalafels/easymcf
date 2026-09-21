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


class Unauthenticated(ApiError):
    status, error = 401, "unauthenticated"


class InvalidCredentials(ApiError):
    status, error = 401, "invalid_credentials"


class Forbidden(ApiError):
    status, error = 403, "forbidden_origin"


class PayloadTooLarge(ApiError):
    status, error = 413, "payload_too_large"


class UnsupportedMedia(ApiError):
    status, error = 415, "unsupported_media_type"


class TooManyAttempts(ApiError):
    status, error = 429, "too_many_attempts"


class GoogleNotConfigured(RecordNotFound):
    error = "google_not_configured"
