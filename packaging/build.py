"""
Build script for SplitForge.
Creates version file, runs PyInstaller, and packages the installer.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Project paths
ROOT = Path(__file__).parent.parent.parent
SRC = ROOT / "src"
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
BUILD = ROOT / "build"

VERSION = "2.0.0"
APP_NAME = "SplitForge"

def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result

def create_version_file():
    """Create version info file for the build."""
    version_file = SRC / "steameditor" / "_version.py"
    content = f'''"""
Auto-generated version file for SplitForge.
Generated at: {datetime.now().isoformat()}
"""
__version__ = "{VERSION}"
__version_tuple__ = ({VERSION.replace(".", ", ")})
__build_date__ = "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
__app_name__ = "{APP_NAME}"
'''
    version_file.write_text(content)
    print(f"Created {version_file}")

def clean_build_dirs():
    """Clean previous build artifacts."""
    for dir_path in [DIST, BUILD, SRC / "steameditor" / "__pycache__"]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"Cleaned {dir_path}")

def copy_resources():
    """Copy resources to build directory."""
    resources_src = ROOT / "src" / "steameditor" / "resources"
    resources_dst = BUILD / "resources"
    if resources_src.exists():
        shutil.copytree(resources_src, resources_dst, dirs_exist_ok=True)
        print(f"Copied resources to {resources_dst}")

    # Copy GIF binaries
    gif_bin_src = ROOT.parent / "GIF" / "bin"
    gif_bin_dst = BUILD / "GIF" / "bin"
    if gif_bin_src.exists():
        shutil.copytree(gif_bin_src, gif_bin_dst, dirs_exist_ok=True)
        print(f"Copied GIF binaries to {gif_bin_dst}")

def run_pyinstaller():
    """Run PyInstaller to build the executable."""
    spec_file = PACKAGING / "pyinstaller" / "steameditor.spec"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]
    run(cmd, cwd=ROOT)

def copy_installer_assets():
    """Copy installer assets to dist."""
    # Copy NSIS script
    nsis_src = PACKAGING / "nsis" / "installer.nsi"
    nsis_dst = DIST / "installer.nsi"
    shutil.copy2(nsis_src, nsis_dst)

    # Copy branding
    branding_src = PACKAGING / "branding"
    branding_dst = DIST / "branding"
    if branding_src.exists():
        shutil.copytree(branding_src, branding_dst, dirs_exist_ok=True)

    # Copy license
    license_src = ROOT / "LICENSE.txt"
    if license_src.exists():
        shutil.copy2(license_src, DIST / "LICENSE.txt")

def build_installer():
    """Build NSIS installer."""
    nsis_path = shutil.which("makensis")
    if not nsis_path:
        # Try common locations
        for path in [
            r"C:\Program Files (x86)\NSIS\makensis.exe",
            r"C:\Program Files\NSIS\makensis.exe",
        ]:
            if Path(path).exists():
                nsis_path = path
                break

    if not nsis_path:
        print("NSIS not found, skipping installer build")
        print("Install NSIS from https://nsis.sourceforge.io/")
        return False

    cmd = [
        nsis_path,
        f"/DVERSION={VERSION}",
        str(DIST / "installer.nsi"),
    ]
    run(cmd, cwd=DIST)
    return True

def main():
    print(f"Building {APP_NAME} v{VERSION}")
    print("=" * 50)

    try:
        clean_build_dirs()
        create_version_file()
        copy_resources()
        run_pyinstaller()
        copy_installer_assets()
        build_installer()
        print("=" * 50)
        print(f"Build complete! Installer in {DIST}")
    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()