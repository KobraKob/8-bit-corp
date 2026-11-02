from typing import Any, Optional


class PixelCorpError(Exception):
    """Base error for Pixel Corp."""

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidStateTransitionError(PixelCorpError):
    """Raised when an illegal task state machine transition is attempted."""
    pass


class CycleDetectedError(PixelCorpError):
    """Raised when delegation DAG contains a cycle."""
    pass


class RateLimitExhaustedError(PixelCorpError):
    """Raised when all rate limit backoffs and fallbacks are exhausted."""
    pass


class ToolExecutionError(PixelCorpError):
    """Raised when a tool execution fails fatally."""
    pass


class SecurityViolationError(PixelCorpError):
    """Raised on path traversal or disallowed sandbox actions."""
    pass
