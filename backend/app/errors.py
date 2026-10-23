class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class NotFoundError(AppError):
    def __init__(self, message: str = "not found"):
        super().__init__("E_NOT_FOUND", message, 404)


class InUseError(AppError):
    def __init__(self, message: str = "in use", status: int = 409):
        super().__init__("E_IN_USE", message, status)


class ConflictError(AppError):
    def __init__(self, message: str = "conflict"):
        super().__init__("E_CONFLICT", message, 409)
