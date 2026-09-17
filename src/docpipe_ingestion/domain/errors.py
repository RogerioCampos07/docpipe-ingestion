class DomainValidationError(ValueError):
    """Raised when a domain model would violate an invariant."""


class InvalidStatusTransitionError(DomainValidationError):
    """Raised when a document status transition is not allowed."""
