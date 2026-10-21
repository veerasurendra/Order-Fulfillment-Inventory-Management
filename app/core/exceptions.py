from typing import Any, Optional


class AppException(Exception):
    """Base exception for application domain errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Any] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class BadRequestError(AppException):
    def __init__(self, message: str, code: str = "BAD_REQUEST", details: Optional[Any] = None):
        super().__init__(code=code, message=message, status_code=400, details=details)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Not authenticated", code: str = "UNAUTHORIZED", details: Optional[Any] = None):
        super().__init__(code=code, message=message, status_code=401, details=details)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Permission denied", code: str = "FORBIDDEN", details: Optional[Any] = None):
        super().__init__(code=code, message=message, status_code=403, details=details)


class ResourceNotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND", details: Optional[Any] = None):
        super().__init__(code=code, message=message, status_code=404, details=details)


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT", details: Optional[Any] = None):
        super().__init__(code=code, message=message, status_code=409, details=details)


# Domain-specific exceptions
class InsufficientInventoryError(AppException):
    def __init__(self, message: str = "Insufficient inventory for product", details: Optional[Any] = None):
        super().__init__(code="INSUFFICIENT_INVENTORY", message=message, status_code=400, details=details)


class InvalidOrderStatusError(AppException):
    def __init__(self, message: str = "Invalid order status transition", details: Optional[Any] = None):
        super().__init__(code="INVALID_ORDER_STATUS", message=message, status_code=400, details=details)


class InvalidReturnStatusError(AppException):
    def __init__(self, message: str = "Invalid return status transition", details: Optional[Any] = None):
        super().__init__(code="INVALID_RETURN_STATUS", message=message, status_code=400, details=details)


class WarehouseAccessDeniedError(AppException):
    def __init__(self, message: str = "Access denied for this warehouse", details: Optional[Any] = None):
        super().__init__(code="WAREHOUSE_ACCESS_DENIED", message=message, status_code=403, details=details)


class ProductInactiveError(AppException):
    def __init__(self, message: str = "Product is inactive and cannot be ordered", details: Optional[Any] = None):
        super().__init__(code="PRODUCT_INACTIVE", message=message, status_code=400, details=details)


class DuplicateIdempotencyKeyError(AppException):
    def __init__(self, message: str = "Concurrent or conflicting request with the same idempotency key", details: Optional[Any] = None):
        super().__init__(code="DUPLICATE_IDEMPOTENCY_KEY", message=message, status_code=409, details=details)


class InvalidInventoryTransferError(AppException):
    def __init__(self, message: str = "Invalid inventory transfer", details: Optional[Any] = None):
        super().__init__(code="INVALID_INVENTORY_TRANSFER", message=message, status_code=400, details=details)


class UserInactiveError(AppException):
    def __init__(self, message: str = "Inactive user cannot authenticate", details: Optional[Any] = None):
        super().__init__(code="USER_INACTIVE", message=message, status_code=403, details=details)
