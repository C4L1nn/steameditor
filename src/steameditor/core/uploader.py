"""uploader.py — Steam Community Upload Automation (Playwright)."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from steameditor.core.models import SteamConfig
from steameditor.events import EventBus

_log = None  # Lazy init to avoid import cycles


def _get_logger():
    global _log
    if _log is None:
        import logging
        _log = logging.getLogger("steameditor.uploader")
    return _log


# ════════════════════════════════════════════════════════════════════
# Status Persistence
# ════════════════════════════════════════════════════════════════════

def status_path_for(manifest_path: str | Path) -> Path:
    return Path(manifest_path).with_suffix(".status.json")


def write_status(path: Path, **data) -> None:
    current = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current.update(data)
    current["updated_at"] = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_event(path: Path, message: str) -> None:
    current = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    events = current.get("events", [])
    events.append({"time": time.time(), "message": message})
    current["events"] = events[-200:]
    current["updated_at"] = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ════════════════════════════════════════════════════════════════════
# Page Interaction Helpers
# ════════════════════════════════════════════════════════════════════

def choose_file_input(page):
    inputs = page.locator("input[type='file']")
    count = inputs.count()
    if count == 0:
        return None
    for i in range(count):
        candidate = inputs.nth(i)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            pass
    return inputs.first


def fill_title(page, title: str) -> Optional[str]:
    selectors = [
        "#title",
        "input[id*='title']",
        "input[name*='title']",
        "input[name='title']",
        "input[name='name']",
        "input[type='text']",
        "textarea[name='title']",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                locator.fill(title, timeout=5000)
                return selector
        except Exception:
            continue
    return None


_AGREEMENT_TOKENS = (
    "agree", "terms", "tos", "subscriber", "workshop",
    "kabul", "sözleşme", "sozlesme", "onay", "şart", "sart",
)


def check_required_boxes(page):
    clicked = []
    skipped = []
    try:
        boxes = page.locator("input[type='checkbox']")
        for i in range(boxes.count()):
            box = boxes.nth(i)
            try:
                if not box.is_visible() or box.is_checked():
                    continue
                context_text = box.evaluate(
                    """
                    el => {
                        const label_for = el.id
                            ? (document.querySelector(`label[for='${el.id}']`)?.innerText || '')
                            : '';
                        const label_parent = el.closest('label')?.innerText || '';
                        return [el.id, el.name, label_for, label_parent].join(' ').toLowerCase();
                    }
                    """
                ) or ""
                if any(tok in context_text for tok in _AGREEMENT_TOKENS):
                    box.check(timeout=3000)
                    clicked.append(i)
                else:
                    skipped.append(context_text.strip()[:60] or f"checkbox#{i}")
            except Exception:
                pass
    except Exception:
        pass
    if skipped:
        _get_logger().info(f"{len(skipped)} checkbox skipped (not agreement): {skipped}")
    return clicked


def render_title(template: Optional[str], file_path: str, index: int) -> str:
    stem = Path(file_path).stem
    title = template or "{stem}"
    return (
        title
        .replace("{stem}", stem)
        .replace("{name}", stem)
        .replace("{index}", str(index))
        .replace("{index02}", f"{index:02}")
    )


def click_submit(page) -> Optional[str]:
    selectors = [
        "#SubmitItemBtn",
        "#submit",
        "#save",
        "text=Kaydet ve Devam Et",
        "a:has-text('Kaydet ve Devam Et')",
        "button:has-text('Kaydet ve Devam Et')",
        "input[value='Kaydet ve Devam Et']",
        "text=Save and Continue",
        "a:has-text('Save and Continue')",
        "button:has-text('Save and Continue')",
        "input[value='Save and Continue']",
        "a.btn_green_white_innerfade",
        ".btn_green_white_innerfade",
        "input[type='submit']",
        "button[type='submit']",
        "button:has-text('Save')",
        "button:has-text('Upload')",
        "button:has-text('Publish')",
        "button:has-text('Kaydet')",
        "button:has-text('Yükle')",
        "button:has-text('Yayınla')",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                locator.click(timeout=5000)
                return selector
        except Exception:
            continue
    try:
        clicked = page.evaluate(
            """
            () => {
                const wanted = [
                    'Kaydet ve Devam Et',
                    'Save and Continue',
                    'Yayınla',
                    'Publish',
                    'Upload',
                    'Yükle',
                    'Save',
                    'Kaydet'
                ];
                const els = Array.from(document.querySelectorAll('a,button,input[type=submit],input[type=button]'));
                for (const el of els) {
                    const text = ((el.innerText || el.value || el.textContent || '')).trim();
                    if (!text) continue;
                    if (wanted.some(w => text.toLowerCase().includes(w.toLowerCase()))) {
                        el.click();
                        return text;
                    }
                }
                return '';
            }
            """
        )
        if clicked:
            return f"text-fallback:{clicked}"
    except Exception:
        pass
    return None


def upload_success_detected(page, old_url: Optional[str] = None) -> bool:
    url = page.url.lower()
    try:
        body = page.locator("body").inner_text(timeout=2000).lower()
    except Exception:
        body = ""
    success_tokens = (
        "fileuploadsuccess=1",
        "sharedfiles/filedetails",
    )
    success_text = (
        "automatic content",
        "successfully",
        "published",
    )
    if any(token in url for token in success_tokens):
        return True
    if old_url and url == old_url.lower():
        return False
    return any(token in body for token in success_text)


def upload_error_detected(page) -> str:
    try:
        body = page.locator("body").inner_text(timeout=2000).lower()
    except Exception:
        return ""
    error_tokens = (
        "error",
        "hata",
        "failed",
        "try again",
        "tekrar deneyin",
        "file upload failed",
    )
    for token in error_tokens:
        if token in body:
            return token
    return ""


def wait_for_upload_result(page, old_url: str, timeout_ms: int = 90000) -> bool:
    deadline = time.time() + (timeout_ms / 1000)
    last_error = ""
    while time.time() < deadline:
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        if upload_success_detected(page, old_url):
            _get_logger().info("Upload success page detected.")
            return True
        last_error = upload_error_detected(page) or last_error
        time.sleep(1)
    if last_error:
        raise RuntimeError(f"Steam upload did not complete; error signal: {last_error}")
    raise RuntimeError("Steam upload timed out; success page not reached.")


def wait_for_manual_success(page, timeout_ms: int = 1800000) -> None:
    _get_logger().info("Waiting for manual submission... Upload must complete within timeout.")
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        url = page.url.lower()
        try:
            body = page.locator("body").inner_text(timeout=2000).lower()
        except Exception:
            body = ""
        if (
            "fileuploadsuccess=1" in url
            or "success" in url
            or "başarı" in body
            or "automatic content" in body
        ):
            _get_logger().info("Upload success page detected.")
            return
        time.sleep(1)
    raise RuntimeError(f"Manual upload did not complete within {int(timeout_ms/60000)} minutes; piece skipped.")


def wait_for_steam_login(page):
    if "login" not in page.url.lower():
        return
    _get_logger().info("Steam login page detected. Please log in to continue.")
    page.wait_for_url(lambda url: "login" not in url.lower(), timeout=10 * 60 * 1000)


def capture_steam_showcase_preview(
    piece_paths: list[Path | str],
    parts_per_row: int = 5,
    timeout_ms: int = 15000,
) -> "Image.Image | None":
    """Gerçek Steam vitrin DOM'u ile canlı önizleme — Playwright headless.

    Parçaları Steam profil vitrinini taklit eden minimal HTML'e inject edip
    screenshot alır. Playwright yoksa veya hata olursa None döner (fallback
    `render_showcase_preview` kullanılsın).
    """
    if not piece_paths:
        return None
    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image
    except Exception as e:
        _get_logger().debug(f"Live preview: playwright/PIL yok: {e}")
        return None

    # Encode images to data URLs (avoid file:// CORS)
    data_urls: list[str] = []
    for p in piece_paths:
        try:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            ext = Path(p).suffix.lower().lstrip(".") or "png"
            if ext == "jpg":
                ext = "jpeg"
            data_urls.append(f"data:image/{ext};base64,{b64}")
        except Exception as e:
            _get_logger().warning(f"Live preview encode hatası {p}: {e}")
            return None

    parts_per_row = max(1, int(parts_per_row))
    # Steam vitrin CSS'i taklit eden minimal HTML
    # Gerçek Steam: .workshopShowcase, gap 4px, bg #171a21, radius 4px
    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
    <style>
      body{{margin:0;padding:24px;background:#171a21;font-family:Arial,sans-serif}}
      .header{{color:#66c0f4;font-size:14px;margin-bottom:12px;letter-spacing:1px}}
      .showcase{{background:#1b2838;border-radius:4px;padding:16px;box-shadow:0 0 8px #0008}}
      .grid{{display:grid;grid-template-columns:repeat({parts_per_row},1fr);gap:4px}}
      .grid img{{width:100%;height:auto;display:block;border-radius:2px;background:#0f141f}}
      .footer{{color:#8f98a0;font-size:11px;margin-top:12px;text-align:center}}
    </style></head><body>
      <div class='header'>ATÖLYE VİTRİNİ — CANLI ÖNİZLEME</div>
      <div class='showcase'><div class='grid'>
        {''.join(f"<img src='{u}'/>" for u in data_urls)}
      </div></div>
      <div class='footer'>Steam profil vitrini simülasyonu — yüklemeden önce kontrol</div>
    </body></html>"""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 920, "height": 700})
            page = ctx.new_page()
            page.set_content(html, wait_until="networkidle", timeout=timeout_ms)
            # Grid'e odaklı screenshot
            loc = page.locator(".showcase")
            # loc.screenshot yerine page screenshot + crop daha stabil
            png_bytes = loc.screenshot(timeout=timeout_ms)
            browser.close()
            img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            _get_logger().info(f"Live Steam preview captured: {img.size}")
            return img
    except Exception as e:
        _get_logger().warning(f"Live preview captura hatası: {e}")
        return None


# ════════════════════════════════════════════════════════════════════
# Main Upload Runner
# ════════════════════════════════════════════════════════════════════

class UploadError(Exception):
    def __init__(self, message: str, recoverable: bool = True):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


def run_upload(manifest_path: str | Path, steam_cfg: SteamConfig, event_bus: Optional[EventBus] = None) -> bool:
    """
    Run the Steam Community upload process.
    Returns True if all uploads succeeded, False otherwise.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

    manifest = read_manifest(Path(manifest_path))
    status_path = status_path_for(manifest_path)

    files = [f["path"] for f in manifest.get("files", []) if os.path.exists(f.get("path", ""))]
    if not files:
        raise UploadError("No valid files in manifest", recoverable=False)

    sc = manifest.get("steam_community", {})
    url = sc.get("url") or "https://steamcommunity.com/sharedfiles/edititem/767/3/"
    js_snippet = sc.get("console_snippet", "")
    auto_submit = bool(sc.get("auto_submit", False))
    wait_after_ms = int(sc.get("wait_after_upload_ms", 1200))
    title_template = sc.get("title_template", "\u200e ")
    profile_dir = sc.get("profile_dir") or str(Path(manifest_path).parent / ".steam_browser_profile")

    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    _get_logger().info(f"Steam Community uploader started. Files: {len(files)}")
    _get_logger().info(f"Profile: {profile_dir}")
    _get_logger().info(f"Page: {url}")
    write_status(
        status_path,
        state="running",
        total=len(files),
        current=0,
        current_file="",
        completed=[],
        failed=[],
        manifest=str(manifest_path),
    )
    append_event(status_path, f"Uploader started. File count: {len(files)}")

    bus = event_bus or EventBus()

    try:
        with sync_playwright() as p:
            launch_kwargs = {
                "user_data_dir": profile_dir,
                "headless": False,
                "accept_downloads": True,
            }
            context = None
            for channel in ("msedge", "chrome"):
                try:
                    context = p.chromium.launch_persistent_context(channel=channel, **launch_kwargs)
                    break
                except Exception:
                    context = None
            if context is None:
                context = p.chromium.launch_persistent_context(**launch_kwargs)

            page = context.pages[0] if context.pages else context.new_page()

            for index, file_path in enumerate(files, start=1):
                try:
                    _get_logger().info(f"[{index}/{len(files)}] Opening: {url}")
                    write_status(status_path, state="running", current=index, current_file=file_path)
                    append_event(status_path, f"{index}/{len(files)} preparing: {Path(file_path).name}")
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    wait_for_steam_login(page)

                    if js_snippet:
                        try:
                            page.evaluate(js_snippet)
                            _get_logger().info("Console snippet executed.")
                            append_event(status_path, "Console snippet executed.")
                        except Exception as e:
                            _get_logger().error(f"Console snippet error: {e}")
                            append_event(status_path, f"Console snippet error: {e}")

                    try:
                        page.wait_for_selector("input[type='file']", timeout=60000)
                    except PlaywrightTimeoutError:
                        raise UploadError("File input not found. Steam page may have changed or login incomplete.")

                    file_input = choose_file_input(page)
                    if file_input is None:
                        raise UploadError("File input not found.")

                    file_input.set_input_files(file_path)
                    _get_logger().info(f"File selected: {file_path}")
                    append_event(status_path, f"File selected: {Path(file_path).name}")
                    page.wait_for_timeout(wait_after_ms)

                    title = render_title(title_template, file_path, index)
                    title_selector = fill_title(page, title)
                    if title_selector:
                        visible_title = title if title.strip() else "(invisible char)"
                        _get_logger().info(f"Title filled: {visible_title}")
                        append_event(status_path, f"Title filled: {visible_title}")
                    else:
                        _get_logger().warning("Title field not found.")
                        append_event(status_path, "Title field not found.")

                    boxes = check_required_boxes(page)
                    if boxes:
                        _get_logger().info(f"{len(boxes)} checkboxes checked.")
                        append_event(status_path, f"{len(boxes)} checkboxes checked.")

                    if auto_submit:
                        old_url = page.url
                        clicked = click_submit(page)
                        if clicked:
                            _get_logger().info(f"Submit clicked: {clicked}")
                            append_event(status_path, f"Submit clicked: {clicked}")
                            wait_for_upload_result(page, old_url)
                            page.wait_for_timeout(max(wait_after_ms, 2500))
                        else:
                            _get_logger().warning("Submit button not found; waiting for manual.")
                            append_event(status_path, "Submit button not found; waiting for manual.")
                            write_status(status_path, state="waiting", current=index, current_file=file_path)
                            wait_for_manual_success(page)
                    else:
                        _get_logger().info("Auto-submit disabled; waiting for manual submission.")
                        write_status(status_path, state="waiting", current=index, current_file=file_path)
                        wait_for_manual_success(page)

                    current_status = {}
                    try:
                        current_status = json.loads(status_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                    completed = current_status.get("completed", [])
                    completed.append(file_path)
                    write_status(status_path, state="running", completed=completed)
                    append_event(status_path, f"{index}/{len(files)} uploaded: {Path(file_path).name}")

                except Exception as e:
                    current_status = {}
                    try:
                        current_status = json.loads(status_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                    failed = current_status.get("failed", [])
                    failed.append({"path": file_path, "error": str(e)})
                    write_status(status_path, state="failed", current=index, current_file=file_path, failed=failed, error=str(e))
                    append_event(status_path, f"Error: {Path(file_path).name} | {e}")
                    bus.emit("upload.error", {"file": file_path, "error": str(e), "index": index})
                    raise

            _get_logger().info("Automation complete. Browser can be closed.")
            write_status(status_path, state="done", current=len(files), current_file="")
            append_event(status_path, "All pieces completed.")
            bus.emit("upload.complete", {"manifest": str(manifest_path)})
            context.close()
            return True

    except UploadError as e:
        _get_logger().error(f"Upload error: {e.message}")
        write_status(status_path, state="error", error=e.message)
        bus.emit("upload.error", {"error": e.message, "recoverable": e.recoverable})
        return False
    except Exception as e:
        _get_logger().exception("Unexpected error during upload")
        write_status(status_path, state="error", error=str(e))
        bus.emit("upload.error", {"error": str(e), "recoverable": True})
        return False


# ════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--steam-api-key", default="")
    parser.add_argument("--steam-app-id", default="")
    parser.add_argument("--steam-published-file-id", default="")
    args = parser.parse_args()

    steam_cfg = SteamConfig(
        api_key=args.steam_api_key,
        app_id=args.steam_app_id,
        published_file_id=args.steam_published_file_id,
    )

    success = run_upload(args.manifest, steam_cfg)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()