"""SplitForge — Steam Showcase Studio.

A professional desktop application for creating Steam Workshop showcase images
with automated upload to Steam Community.
"""

__version__ = "2.0.0"
__author__ = "Aykut"
__license__ = "MIT"

# Initialize logging early
from steameditor.services.log_service import setup_logging
setup_logging()

# Set up exception handling
from steameditor.error_handler import setup_exception_handling
setup_exception_handling()

# Expose main entry point
from steameditor.ui.app import main

__all__ = ["main"]