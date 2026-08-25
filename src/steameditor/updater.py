"""
Auto-updater for SplitForge.
Checks for updates on GitHub releases and downloads/installs them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from steameditor.services.log_service import get_logger

_log = get_logger("updater")


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        version: str,
        release_url: str,
        download_url: str,
        release_notes: str = "",
        published_at: str = "",
    ):
        self.version = version
        self.release_url = release_url
        self.download_url = download_url
        self.release_notes = release_notes
        self.published_at = published_at

    @classmethod
    def from_github_release(cls, data: dict) -> UpdateInfo:
        """Create from GitHub release API response."""
        assets = data.get("assets", [])
        download_url = ""
        for asset in assets:
            if asset.get("name", "").endswith(".exe"):
                download_url = asset.get("browser_download_url", "")
                break

        return cls(
            version=data.get("tag_name", "").lstrip("v"),
            release_url=data.get("html_url", ""),
            download_url=download_url,
            release_notes=data.get("body", ""),
            published_at=data.get("published_at", ""),
        )

    def is_newer_than(self, current_version: str) -> bool:
        """Check if this version is newer than current."""
        try:
            current = tuple(map(int, current_version.split(".")))
            new = tuple(map(int, self.version.split(".")))
            return new > current
        except Exception:
            return False


class Updater:
    """Handles checking for and applying updates."""

    GITHUB_API_URL = "https://api.github.com/repos/aykut/steameditor/releases/latest"
    GITHUB_REPO_URL = "https://github.com/aykut/steameditor"
    UPDATE_CHECK_INTERVAL = 24 * 60 * 60  # 24 hours

    def __init__(self, current_version: str, install_dir: Path):
        self.current_version = current_version
        self.install_dir = Path(install_dir)
        self._last_check_file = self.install_dir / ".last_update_check"
        self._update_available: Optional[UpdateInfo] = None
        self._check_thread: Optional[threading.Thread] = None

    def check_for_updates(self, force: bool = False) -> Optional[UpdateInfo]:
        """Check for available updates."""
        # Check if enough time has passed since last check
        if not force and self._last_check_file.exists():
            try:
                last_check = float(self._last_check_file.read_text().strip())
                if time.time() - last_check < self.UPDATE_CHECK_INTERVAL:
                    _log.info("Skipping update check (checked recently)")
                    return self._update_available
            except Exception:
                pass

        _log.info("Checking for updates...")
        self._last_check_file.write_text(str(time.time()))

        try:
            req = Request(
                self.GITHUB_API_URL,
                headers={"User-Agent": "SplitForge-Updater/2.0"},
            )
            with urlopen(req, timeout=10) as response:
                data = json.load(response)

            update_info = UpdateInfo.from_github_release(data)

            if update_info.is_newer_than(self.current_version):
                _log.info(f"Update available: {update_info.version}")
                self._update_available = update_info
                return update_info
            else:
                _log.info("Already on latest version")
                return None

        except (URLError, HTTPError, json.JSONDecodeError, KeyError) as e:
            _log.warning(f"Update check failed: {e}")
            return None
        except Exception as e:
            _log.error(f"Unexpected error during update check: {e}")
            return None

    def check_for_updates_async(self, callback: Optional[callable] = None):
        """Check for updates in background thread."""

        def _check():
            try:
                update = self.check_for_updates()
                if callback:
                    callback(update)
            except Exception as e:
                _log.error(f"Async update check failed: {e}")
                if callback:
                    callback(None)

        self._check_thread = threading.Thread(target=_check, daemon=True)
        self._check_thread.start()

    def download_update(self, update_info: UpdateInfo, progress_callback: Optional[callable] = None) -> Optional[Path]:
        """Download the update installer."""
        if not update_info.download_url:
            _log.error("No download URL available")
            return None

        _log.info(f"Downloading update from {update_info.download_url}")

        # Download to temp file
        temp_dir = Path(os.environ.get("TEMP", "."))
        installer_path = temp_dir / f"SplitForge_Setup_{update_info.version}.exe"

        try:
            req = Request(update_info.download_url, headers={"User-Agent": "SplitForge-Updater/2.0"})
            with urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                with open(installer_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)

            _log.info(f"Downloaded to {installer_path}")
            return installer_path

        except Exception as e:
            _log.error(f"Download failed: {e}")
            installer_path.unlink(missing_ok=True)
            return None

    def install_update(self, installer_path: Path) -> bool:
        """Run the installer to apply update."""
        _log.info(f"Installing update from {installer_path}")

        try:
            # Run installer silently
            result = subprocess.run(
                [str(installer_path), "/S", "/D=" + str(self.install_dir)],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            _log.info("Update installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            _log.error(f"Installation failed: {e.stderr}")
            return False
        except Exception as e:
            _log.error(f"Installation error: {e}")
            return False

    def get_update_info(self) -> Optional[UpdateInfo]:
        """Get cached update info."""
        return self._update_available


# Convenience function for manual update check
def check_for_updates(current_version: str, install_dir: str | Path) -> Optional[UpdateInfo]:
    """Check for updates synchronously."""
    updater = Updater(current_version, Path(install_dir))
    return updater.check_for_updates()