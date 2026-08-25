"""steameditor.ui — UI paketi."""

from steameditor.ui.design_system import (
    apply_theme, COLORS, SPACING, TYPO, RADIUS, SHADOWS,
)
from steameditor.ui.app_shell import App


def main():
    apply_theme()
    app = App()
    app.mainloop()


__all__ = [
    "main",
    "App",
    "apply_theme",
    "COLORS", "SPACING", "TYPO", "RADIUS", "SHADOWS",
]
