"""steameditor.exceptions — Exception hierarchy."""

from __future__ import annotations


class SteamEditorError(Exception):
    """Base exception with user-facing message and technical details."""

    def __init__(
        self,
        user_message: str,
        technical_details: str = "",
        recoverable: bool = True,
        error_code: str = "GENERIC_ERROR",
    ):
        self.user_message = user_message
        self.technical_details = technical_details
        self.recoverable = recoverable
        self.error_code = error_code
        super().__init__(user_message)

    def __str__(self) -> str:
        return self.user_message


class TemplateError(SteamEditorError):
    """Template-related errors (validation, missing, etc.)"""

    def __init__(self, message: str, details: str = "", recoverable: bool = True):
        super().__init__(message, details, recoverable, "TEMPLATE_ERROR")


class ProcessingError(SteamEditorError):
    """Image/GIF processing errors."""

    def __init__(self, message: str, details: str = "", recoverable: bool = True):
        super().__init__(message, details, recoverable, "PROCESSING_ERROR")


class UploadError(SteamEditorError):
    """Steam Community upload errors."""

    def __init__(self, message: str, details: str = "", recoverable: bool = True):
        super().__init__(message, details, recoverable, "UPLOAD_ERROR")


class ConfigError(SteamEditorError):
    """Configuration loading/saving errors."""

    def __init__(self, message: str, details: str = "", recoverable: bool = True):
        super().__init__(message, details, recoverable, "CONFIG_ERROR")


class BinaryMissingError(SteamEditorError):
    """Required external binary (ffmpeg, gifsicle, etc.) not found."""

    def __init__(self, binary: str, install_hint: str):
        message = f"Gerekli araç bulunamadı: {binary}"
        details = f"{binary} not found in PATH or bundled location"
        super().__init__(message, details, recoverable=True, error_code="BINARY_MISSING")
        self.binary = binary
        self.install_hint = install_hint


class ProjectError(SteamEditorError):
    """Project load/save errors."""

    def __init__(self, message: str, details: str = "", recoverable: bool = True):
        super().__init__(message, details, recoverable, "PROJECT_ERROR")


class ProfileError(SteamEditorError):
    """Profile load/save errors."""

    def __init__(self, message: str, details: str = "", recoverable: bool = True):
        super().__init__(message, details, recoverable, "PROFILE_ERROR")


class ValidationError(SteamEditorError):
    """Data validation errors (Pydantic, etc.)"""

    def __init__(self, message: str, details: str = "", field: str = ""):
        super().__init__(message, details, recoverable=True, error_code="VALIDATION_ERROR")
        self.field = field


# Convenience function for handling any exception
def handle_exception(exc: Exception, context: str = "") -> SteamEditorError:
    """Convert any exception to a SteamEditorError with context."""
    if isinstance(exc, SteamEditorError):
        if context and exc.technical_details:
            exc.technical_details = f"{context}: {exc.technical_details}"
        elif context:
            exc.technical_details = context
        return exc

    # Map common exceptions
    import errno
    import subprocess

    if isinstance(exc, FileNotFoundError):
        return ProcessingError(
            f"Dosya bulunamadı: {exc.filename}",
            f"FileNotFoundError: {exc}",
            recoverable=True,
        )
    if isinstance(exc, PermissionError):
        return ProcessingError(
            f"Erişim reddedildi: {exc.filename}",
            f"PermissionError: {exc}",
            recoverable=False,
        )
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return ProcessingError(
            "Disk alanı yetersiz.",
            f"OSError: {exc}",
            recoverable=False,
        )
    if isinstance(exc, MemoryError):
        return ProcessingError(
            "Yetersiz bellek. Daha küçük görseller deneyin.",
            f"MemoryError: {exc}",
            recoverable=False,
        )
    if isinstance(exc, subprocess.CalledProcessError):
        return ProcessingError(
            f"Harici araç hatası (exit code {exc.returncode})",
            f"CalledProcessError: {exc.cmd} -> {exc.stderr}",
            recoverable=True,
        )

    # Generic fallback
    return SteamEditorError(
        f"Beklenmeyen hata: {type(exc).__name__}",
        f"{context}: {exc}" if context else str(exc),
        recoverable=True,
    )


__all__ = [
    "SteamEditorError",
    "TemplateError",
    "ProcessingError",
    "UploadError",
    "ConfigError",
    "BinaryMissingError",
    "ProjectError",
    "ProfileError",
    "ValidationError",
    "handle_exception",
]