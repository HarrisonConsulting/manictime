class ManicTimeClientError(Exception):
    """Base exception for ManicTime client errors"""
    pass

class AuthenticationError(ManicTimeClientError):
    """Authentication related errors"""
    pass

class NotFoundError(ManicTimeClientError):
    """Resource not found errors"""
    pass