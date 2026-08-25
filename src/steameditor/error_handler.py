"""steameditor.error_handler — Centralized error handling and crash reporting."""

from __future__ import annotations

import sys
import traceback
import threading
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass, asdict

from steameditor.services import get_config_service
from steameditor.exceptions import SteamEditorError, handle_exception
from steameditor.events import get_event_bus, emit


@dataclass
class CrashReport:
    """Structured crash report for diagnostics."""
    timestamp: str
    version: str
    platform: str
    python_version: str
    exception_type: str
    exception_message: str
    traceback: str
    context: str
    user_message: str
    recoverable: bool
    error_code: str
    system_info: dict

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")


class ErrorHandler:
    """Centralized error handling with crash reporting."""

    _instance: Optional[ErrorHandler] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._crash_dir: Path = self._get_crash_dir()
        self._callbacks: list[Callable[[CrashReport], None]] = []
        self._gui_callback: Optional[Callable[[str, str], None]] = None
        self._initialized = True

    def _get_crash_dir(self) -> Path:
        config = get_config_service()
        return config.config_dir / "crashes"

    def register_gui_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for showing error dialogs in GUI."""
        self._gui_callback = callback

    def register_crash_callback(self, callback: Callable[[CrashReport], None]) -> None:
        """Register callback for custom crash handling."""
        self._callbacks.append(callback)

    def handle(self, exc: Exception, context: str = "") -> CrashReport:
        """Handle any exception, create crash report, notify callbacks."""
        se_error = handle_exception(exc, context)

        # Create crash report
        report = CrashReport(
            timestamp=datetime.now().isoformat(),
            version=self._get_version(),
            platform=sys.platform,
            python_version=sys.version.split()[0],
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            context=context,
            user_message=se_error.user_message,
            recoverable=se_error.recoverable,
            error_code=se_error.error_code,
            system_info=self._get_system_info(),
        )

        # Save report
        self._save_report(report)

        # Notify callbacks
        for cb in self._callbacks:
            try:
                cb(report)
            except Exception:
                pass

        # Emit event
        emit("error.crashed", report)

        # Show GUI dialog if callback registered
        if self._gui_callback and not getattr(sys, 'frozen', False) or True:
            try:
                self._gui_callback(se_error.user_message, se_error.technical_details)
            except Exception:
                pass

        return report

    def _save_report(self, report: CrashReport) -> None:
        """Save crash report to disk."""
        try:
            filename = f"crash_{report.timestamp.replace(':', '-').replace('.', '-')}.json"
            path = self._crash_dir / filename
            report.save(path)
        except Exception:
            pass

    def _get_version(self) -> str:
        try:
            from steameditor import __version__
            return __version__
        except ImportError:
            return "2.0.0"

    def _get_system_info(self) -> dict:
        import platform
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture(),
        }

    def get_recent_crashes(self, limit: int = 10) -> list[CrashReport]:
        """Load recent crash reports."""
        crashes = []
        if not self._crash_dir.exists():
            return crashes
        for path in sorted(self._crash_dir.glob("crash_*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                crashes.append(CrashReport(**data))
            except Exception:
                pass
        return crashes


# Global error handler
_error_handler: ErrorHandler | None = None


def get_error_handler() -> ErrorHandler:
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def setup_exception_handling(gui_callback: Optional[Callable[[str, str], None]] = None) -> None:
    """Set up global exception handlers."""
    handler = get_error_handler()
    if gui_callback:
        handler.register_gui_callback(gui_callback)

    def handle_exception_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        handler.handle(exc_value, "Unhandled exception")

    sys.excepthook = handle_exception_hook

    # Also handle threading exceptions
    def handle_thread_exception(args):
        handler.handle(args.exc_value, f"Thread exception in {args.thread.name}")

    threading.excepthook = handle_thread_exception


def show_error_dialog(title: str, message: str, details: str = "") -> None:
    """Show error dialog (uses tkinter if GUI available)."""
    try:
        import customtkinter as ctk
        from tkinter import messagebox

        # Create minimal root if needed
        root = ctk.CTk()
        root.withdraw()

        if details:
            full_msg = f"{message}\n\nDetaylar:\n{details}"
        else:
            full_msg = message

        messagebox.showerror(title, full_msg)
        root.destroy()
    except Exception:
        # Fallback to console
        print(f"ERROR: {title}")
        print(f"Message: {message}")
        if details:
            print(f"Details: {details}")