#!/usr/bin/env bash
# Cross-platform build script for SplitForge
# Usage: ./build_cross_platform.sh [windows|linux|macos|all]

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="$ROOT_DIR/src"
PACKAGING_DIR="$ROOT_DIR/packaging"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"

VERSION="2.0.0"
APP_NAME="SplitForge"

PYTHON_VERSION="3.11"
PYINSTALLER_VERSION="6.1.0"

echo "=========================================="
echo "Building SplitForge v$VERSION"
echo "=========================================="

# Parse arguments
TARGETS=()
if [ $# -eq 0 ]; then
    TARGETS=("windows" "linux" "macos")
else
    TARGETS=("$@")
fi

# Detect current OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux" ;;
        Darwin*)    echo "macos" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

CURRENT_OS=$(detect_os)
echo "Current OS: $CURRENT_OS"

# Clean build directories
clean_dirs() {
    echo "Cleaning build directories..."
    rm -rf "$DIST_DIR" "$BUILD_DIR"
    mkdir -p "$DIST_DIR" "$BUILD_DIR"
}

# Copy resources
copy_resources() {
    echo "Copying resources..."
    mkdir -p "$BUILD_DIR/resources"
    cp -r "$SRC_DIR/steameditor/resources"/* "$BUILD_DIR/resources/" 2>/dev/null || true
    cp -r "$ROOT_DIR/GIF/bin" "$BUILD_DIR/GIF/bin" 2>/dev/null || true
    cp "$ROOT_DIR/app_icon.ico" "$BUILD_DIR/" 2>/dev/null || true
    cp "$ROOT_DIR/app_icon.png" "$BUILD_DIR/" 2>/dev/null || true
}

# Build with PyInstaller
build_pyinstaller() {
    local target=$1
    local spec_file="$PACKAGING_DIR/pyinstaller/steameditor.spec"
    
    echo "Building for $target with PyInstaller..."
    
    cd "$ROOT_DIR"
    
    # Platform-specific options
    local pyinstaller_args=(
        "--clean"
        "--noconfirm"
        "--distpath=$DIST_DIR/$target"
        "--workpath=$BUILD_DIR/$target"
        "--specpath=$BUILD_DIR/$target"
    )
    
    case $target in
        windows)
            pyinstaller_args+=(
                "--name=SplitForge"
                "--icon=$SRC_DIR/steameditor/resources/app_icon.ico"
                "--add-data=$SRC_DIR/steameditor/resources:resources"
                "--add-data=$SRC_DIR/steameditor/plugins.py:steameditor"
                "--add-data=$ROOT_DIR/GIF/bin:GIF/bin"
                "--hidden-import=steameditor.core.models"
                "--hidden-import=steameditor.core.processor"
                "--hidden-import=steameditor.core.uploader"
                "--hidden-import=steameditor.services.config_service"
                "--hidden-import=steameditor.services.worker_pool"
                "--hidden-import=steameditor.services.image_cache"
                "--hidden-import=steameditor.services.log_service"
                "--hidden-import=steameditor.events"
                "--hidden-import=steameditor.plugins"
                "--hidden-import=steameditor.plugins.BuiltinEffectPlugin"
                "--hidden-import=steameditor.plugins.BorderTemplateEditor"
                "--hidden-import=steameditor.plugins.ColorPaletteManager"
                "--hidden-import=steameditor.plugins.AnimationTimeline"
                "--hidden-import=steameditor.ui.app"
                "--hidden-import=steameditor.ui.components"
                "--hidden-import=steameditor.ui.design_system"
                "--hidden-import=steameditor.ui.pages.settings_page"
                "--hidden-import=steameditor.ui.color_palette"
                "--hidden-import=steameditor.plugins"
                "--hidden-import=steameditor.config"
                "--hidden-import=steameditor.config_legacy"
                "--hidden-import=steameditor.updater"
                "--hidden-import=steameditor.error_handler"
                "--hidden-import=steameditor.exceptions"
                "--hidden-import=playwright.sync_api"
                "--hidden-import=PIL._imaging"
                "--hidden-import=PIL.Image"
                "--hidden-import=PIL.ImageDraw"
                "--hidden-import=PIL.ImageFont"
                "--hidden-import=PIL.ImageFilter"
                "--hidden-import=PIL.ImageEnhance"
                "--hidden-import=PIL.ImageChops"
                "--hidden-import=PIL.ImageOps"
                "--hidden-import=PIL.ImageSequence"
                "--hidden-import=PIL.ImageTk"
                "--hidden-import=PIL.JpegImagePlugin"
                "--hidden-import=PIL.PngImagePlugin"
                "--hidden-import=PIL.GifImagePlugin"
                "--hidden-import=PIL.WebPImagePlugin"
                "--hidden-import=customtkinter"
                "--hidden-import=tkinterdnd2"
                "--hidden-import=pydantic"
                "--hidden-import=pydantic_core"
                "--hidden-import=pydantic_settings"
                "--noconsole"
                "--windowed"
            )
            ;;
        linux)
            pyinstaller_args+=(
                "--name=SplitForge"
                "--icon=$SRC_DIR/steameditor/resources/app_icon.png"
                "--add-data=$SRC_DIR/steameditor/resources:resources"
                "--add-data=$SRC_DIR/steameditor/plugins.py:steameditor"
                "--add-data=$ROOT_DIR/GIF/bin:GIF/bin"
                "--hidden-import=steameditor.core.models"
                "--hidden-import=steameditor.core.processor"
                "--hidden-import=steameditor.core.uploader"
                "--hidden-import=steameditor.services.config_service"
                "--hidden-import=steameditor.services.worker_pool"
                "--hidden-import=steameditor.services.image_cache"
                "--hidden-import=steameditor.services.log_service"
                "--hidden-import=steameditor.events"
                "--hidden-import=steameditor.plugins"
                "--hidden-import=steameditor.plugins.BuiltinEffectPlugin"
                "--hidden-import=steameditor.plugins.BorderTemplateEditor"
                "--hidden-import=steameditor.plugins.ColorPaletteManager"
                "--hidden-import=steameditor.plugins.AnimationTimeline"
                "--hidden-import=steameditor.ui.app"
                "--hidden-import=steameditor.ui.components"
                "--hidden-import=steameditor.ui.design_system"
                "--hidden-import=steameditor.ui.pages.settings_page"
                "--hidden-import=steameditor.ui.color_palette"
                "--hidden-import=steameditor.plugins"
                "--hidden-import=steameditor.config"
                "--hidden-import=steameditor.config_legacy"
                "--hidden-import=steameditor.updater"
                "--hidden-import=steameditor.error_handler"
                "--hidden-import=steameditor.exceptions"
                "--hidden-import=playwright.sync_api"
                "--hidden-import=PIL._imaging"
                "--hidden-import=PIL.Image"
                "--hidden-import=PIL.ImageDraw"
                "--hidden-import=PIL.ImageFont"
                "--hidden-import=PIL.ImageFilter"
                "--hidden-import=PIL.ImageEnhance"
                "--hidden-import=PIL.ImageChops"
                "--hidden-import=PIL.ImageOps"
                "--hidden-import=PIL.ImageSequence"
                "--hidden-import=PIL.ImageTk"
                "--hidden-import=PIL.JpegImagePlugin"
                "--hidden-import=PIL.PngImagePlugin"
                "--hidden-import=PIL.GifImagePlugin"
                "--hidden-import=PIL.WebPImagePlugin"
                "--hidden-import=customtkinter"
                "--hidden-import=tkinterdnd2"
                "--hidden-import=pydantic"
                "--hidden-import=pydantic_core"
                "--hidden-import=pydantic_settings"
                "--noconsole"
            )
            ;;
        macos)
            pyinstaller_args+=(
                "--name=SplitForge"
                "--icon=$SRC_DIR/steameditor/resources/app_icon.png"
                "--add-data=$SRC_DIR/steameditor/resources:resources"
                "--add-data=$SRC_DIR/steameditor/plugins.py:steameditor"
                "--add-data=$ROOT_DIR/GIF/bin:GIF/bin"
                "--hidden-import=steameditor.core.models"
                "--hidden-import=steameditor.core.processor"
                "--hidden-import=steameditor.core.uploader"
                "--hidden-import=steameditor.services.config_service"
                "--hidden-import=steameditor.services.worker_pool"
                "--hidden-import=steameditor.services.image_cache"
                "--hidden-import=steameditor.services.log_service"
                "--hidden-import=steameditor.events"
                "--hidden-import=steameditor.plugins"
                "--hidden-import=steameditor.plugins.BuiltinEffectPlugin"
                "--hidden-import=steameditor.plugins.BorderTemplateEditor"
                "--hidden-import=steameditor.plugins.ColorPaletteManager"
                "--hidden-import=steameditor.plugins.AnimationTimeline"
                "--hidden-import=steameditor.ui.app"
                "--hidden-import=steameditor.ui.components"
                "--hidden-import=steameditor.ui.design_system"
                "--hidden-import=steameditor.ui.pages.settings_page"
                "--hidden-import=steameditor.ui.color_palette"
                "--hidden-import=steameditor.plugins"
                "--hidden-import=steameditor.config"
                "--hidden-import=steameditor.config_legacy"
                "--hidden-import=steameditor.updater"
                "--hidden-import=steameditor.error_handler"
                "--hidden-import=steameditor.exceptions"
                "--hidden-import=playwright.sync_api"
                "--hidden-import=PIL._imaging"
                "--hidden-import=PIL.Image"
                "--hidden-import=PIL.ImageDraw"
                "--hidden-import=PIL.ImageFont"
                "--hidden-import=PIL.ImageFilter"
                "--hidden-import=PIL.ImageEnhance"
                "--hidden-import=PIL.ImageChops"
                "--hidden-import=PIL.ImageOps"
                "--hidden-import=PIL.ImageSequence"
                "--hidden-import=PIL.ImageTk"
                "--hidden-import=PIL.JpegImagePlugin"
                "--hidden-import=PIL.PngImagePlugin"
                "--hidden-import=PIL.GifImagePlugin"
                "--hidden-import=PIL.WebPImagePlugin"
                "--hidden-import=customtkinter"
                "--hidden-import=tkinterdnd2"
                "--hidden-import=pydantic"
                "--hidden-import=pydantic_core"
                "--hidden-import=pydantic_settings"
                "--noconsole"
                "--windowed"
                "--osx-bundle-identifier=com.aykut.splitforge"
            )
            ;;
    esac
    
    pyinstaller_args+=("$SRC_DIR/steameditor/__main__.py")
    
    echo "Running: pyinstaller ${pyinstaller_args[@]}"
    pyinstaller "${pyinstaller_args[@]}"
}

# Create portable version
create_portable() {
    local target=$1
    local portable_dir="$DIST_DIR/${target}_portable"
    
    echo "Creating portable version for $target..."
    
    mkdir -p "$portable_dir"
    cp -r "$DIST_DIR/$target/SplitForge"* "$portable_dir/"
    
    # Create portable config
    cat > "$portable_dir/portable.ini" << EOF
[Portable]
Enabled=true
ConfigDir=./config
LogDir=./logs
CacheDir=./cache
EOF
    
    mkdir -p "$portable_dir/config" "$portable_dir/logs" "$portable_dir/cache"
    
    # Create launch script
    case $target in
        windows)
            cat > "$portable_dir/SplitForge_Portable.bat" << 'EOF'
@echo off
set LOCALAPPDATA=%~dp0config
set APPDATA=%~dp0config
start "" "%~dp0SplitForge.exe" %*
EOF
            ;;
        linux|macos)
            cat > "$portable_dir/SplitForge_Portable.sh" << 'EOF'
#!/bin/bash
export XDG_CONFIG_HOME="$PWD/config"
export XDG_CACHE_HOME="$PWD/cache"
export XDG_DATA_HOME="$PWD/data"
exec "$PWD/SplitForge" "$@"
EOF
            chmod +x "$portable_dir/SplitForge_Portable.sh"
            ;;
    esac
    
    echo "Portable version created at: $portable_dir"
}

# Create AppImage for Linux
create_appimage() {
    if [ "$CURRENT_OS" != "linux" ]; then
        echo "AppImage creation only supported on Linux"
        return
    fi
    
    echo "Creating AppImage..."
    
    # Install appimagetool if not present
    if ! command -v appimagetool &> /dev/null; then
        wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O /tmp/appimagetool
        chmod +x /tmp/appimagetool
        APPIMAGETOOL=/tmp/appimagetool
    else
        APPIMAGETOOL=appimagetool
    fi
    
    APPDIR="$BUILD_DIR/AppDir"
    mkdir -p "$APPDIR/usr/bin"
    cp -r "$DIST_DIR/linux/SplitForge"/* "$APPDIR/usr/bin/"
    
    # Create .desktop file
    cat > "$APPDIR/SplitForge.desktop" << EOF
[Desktop Entry]
Name=SplitForge
Comment=Steam Workshop Showcase Studio
Exec=SplitForge
Icon=splitforge
Terminal=false
Type=Application
Categories=Graphics;Photography;
StartupNotify=true
EOF
    
    # Copy icon
    cp "$SRC_DIR/steameditor/resources/app_icon.png" "$APPDIR/splitforge.png"
    
    # Create AppRun
    cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
export XDG_DATA_DIRS="$APPDIR/usr/share:$XDG_DATA_DIRS"
export LD_LIBRARY_PATH="$APPDIR/usr/lib:$LD_LIBRARY_PATH"
exec "$APPDIR/usr/bin/SplitForge" "$@"
EOF
    chmod +x "$APPDIR/AppRun"
    
    # Build AppImage
    $APPIMAGETOOL "$APPDIR" "$DIST_DIR/SplitForge-$VERSION-x86_64.AppImage"
    
    echo "AppImage created at: $DIST_DIR/SplitForge-$VERSION-x86_64.AppImage"
}

# Create DMG for macOS
create_dmg() {
    if [ "$CURRENT_OS" != "macos" ]; then
        echo "DMG creation only supported on macOS"
        return
    fi
    
    echo "Creating DMG..."
    
    DMG_DIR="$BUILD_DIR/dmg"
    mkdir -p "$DMG_DIR"
    cp -r "$DIST_DIR/macos/SplitForge.app" "$DMG_DIR/"
    
    # Create symlink to Applications
    ln -s /Applications "$DMG_DIR/Applications"
    
    # Create DMG
    hdiutil create -volname "SplitForge $VERSION" \
        -srcfolder "$DMG_DIR" \
        -ov -format UDZO \
        "$DIST_DIR/SplitForge-$VERSION-macos.dmg"
    
    echo "DMG created at: $DIST_DIR/SplitForge-$VERSION-macos.dmg"
}

# Create portable archive
create_portable_archive() {
    local target=$1
    echo "Creating portable archive for $target..."
    
    case $target in
        windows)
            cd "$DIST_DIR/windows"
            7z a "../SplitForge-${VERSION}-windows-portable.zip" SplitForge/
            ;;
        linux)
            cd "$DIST_DIR/linux"
            tar -czf "../SplitForge-${VERSION}-linux-portable.tar.gz" SplitForge/
            ;;
        macos)
            cd "$DIST_DIR/macos"
            tar -czf "../SplitForge-${VERSION}-macos-portable.tar.gz" SplitForge.app/
            ;;
    esac
}

# Main build function
build_target() {
    local target=$1
    
    echo ""
    echo "=========================================="
    echo "Building for $target"
    echo "=========================================="
    
    clean_dirs
    copy_resources
    build_pyinstaller "$target"
    create_portable "$target"
    
    case $target in
        linux)
            create_appimage
            create_portable_archive "$target"
            ;;
        macos)
            create_dmg
            create_portable_archive "$target"
            ;;
        windows)
            create_portable_archive "$target"
            ;;
    esac
    
    echo "Build for $target completed!"
    echo "Output in: $DIST_DIR/$target"
}

# Main
main() {
    for target in "${TARGETS[@]}"; do
        case $target in
            windows|linux|macos)
                # Check if we can build for this target
                if [ "$target" = "macos" ] && [ "$CURRENT_OS" != "macos" ]; then
                    echo "Warning: Cannot build macOS on $CURRENT_OS"
                    continue
                fi
                if [ "$target" = "windows" ] && [ "$CURRENT_OS" != "windows" ]; then
                    echo "Warning: Cannot build Windows on $CURRENT_OS (cross-compilation not supported)"
                    continue
                fi
                if [ "$target" = "linux" ] && [ "$CURRENT_OS" != "linux" ]; then
                    echo "Warning: Cannot build Linux on $CURRENT_OS (cross-compilation not supported)"
                    continue
                fi
                build_target "$target"
                ;;
            *)
                echo "Unknown target: $target"
                exit 1
                ;;
        esac
    done
    
    echo ""
    echo "=========================================="
    echo "All builds completed!"
    echo "=========================================="
    echo "Artifacts in: $DIST_DIR"
    ls -la "$DIST_DIR"
}

main "$@"