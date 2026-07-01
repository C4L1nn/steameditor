import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        return sync_playwright, PlaywrightTimeoutError
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        return sync_playwright, PlaywrightTimeoutError


def log(msg):
    print(msg, flush=True)


def status_path_for(manifest_path):
    return str(Path(manifest_path).with_suffix(".status.json"))


def write_status(path, **data):
    current = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}
    current.update(data)
    current["updated_at"] = time.time()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def append_event(path, message):
    current = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}
    events = current.get("events", [])
    events.append({"time": time.time(), "message": message})
    current["events"] = events[-200:]
    current["updated_at"] = time.time()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def fill_title(page, title):
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


# Sadece sözleşme/onay niteliğindeki kutular işaretlenir. Eskiden sayfadaki
# TÜM görünür checkbox'lar körlemesine işaretleniyordu — Steam forma yeni bir
# kutu eklerse (örn. içerik beyanı) auto_submit'le birlikte gözetimsiz yanlış
# beyan riski doğuyordu.
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
                # id + name + bağlı label metnini topla, allowlist'e bak
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
        log(f"{len(skipped)} checkbox sözleşme/onay kutusu olmadığı için atlandı: {skipped}")
    return clicked


def render_title(template, file_path, index):
    stem = Path(file_path).stem
    title = template if template is not None else "{stem}"
    return (
        title
        .replace("{stem}", stem)
        .replace("{name}", stem)
        .replace("{index}", str(index))
        .replace("{index02}", f"{index:02}")
    )


def click_submit(page):
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


def upload_success_detected(page, old_url=None):
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


def upload_error_detected(page):
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


def wait_for_upload_result(page, old_url, timeout_ms=90000):
    deadline = time.time() + (timeout_ms / 1000)
    last_error = ""
    while time.time() < deadline:
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        if upload_success_detected(page, old_url):
            log("Upload basari sayfasi algilandi.")
            return True
        last_error = upload_error_detected(page) or last_error
        time.sleep(1)
    if last_error:
        raise RuntimeError(f"Steam upload tamamlanmadi; sayfada hata sinyali var: {last_error}")
    raise RuntimeError("Steam upload tamamlanmadi; basari sayfasi zaman asimina ugradi.")


def wait_for_manual_success(page, timeout_ms=1800000):
    log("Elle gönderimi bekliyorum. Upload tamamlanınca sıradaki parçaya geçeceğim.")
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
            or "otomatik içerik kontrolü" in body
            or "automatic content" in body
        ):
            log("Upload başarı sayfası algılandı.")
            return
        time.sleep(1)
    raise RuntimeError(
        f"Elle gönderim {int(timeout_ms/60000)} dakikada tamamlanmadı; bu parça atlandı."
    )


def wait_for_steam_login(page):
    if "login" not in page.url.lower():
        return
    log("Steam login sayfası açık. Giriş yapınca otomasyon devam edecek.")
    page.wait_for_url(lambda url: "login" not in url.lower(), timeout=10 * 60 * 1000)


def run_upload(manifest_path):
    sync_playwright, PlaywrightTimeoutError = ensure_playwright()
    manifest = read_manifest(manifest_path)
    status_path = status_path_for(manifest_path)

    files = [f["path"] for f in manifest.get("files", []) if os.path.exists(f.get("path", ""))]
    if not files:
        raise RuntimeError("Manifest içinde yüklenecek dosya yok.")

    steam = manifest.get("steam_community", {})
    url = steam.get("url") or "https://steamcommunity.com/sharedfiles/edititem/767/3/"
    js_snippet = steam.get("console_snippet", "")
    auto_submit = bool(steam.get("auto_submit", False))
    wait_after_ms = int(steam.get("wait_after_upload_ms", 1200))
    title_template = steam.get("title_template", "\u200e ")
    profile_dir = steam.get("profile_dir") or str(Path(manifest_path).parent / ".steam_browser_profile")

    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    log(f"Steam Community uploader başladı. Dosya sayısı: {len(files)}")
    log(f"Profil: {profile_dir}")
    log(f"Sayfa: {url}")
    write_status(
        status_path,
        state="running",
        total=len(files),
        current=0,
        current_file="",
        completed=[],
        failed=[],
        manifest=manifest_path,
    )
    append_event(status_path, f"Uploader başladı. Dosya sayısı: {len(files)}")

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
                log(f"[{index}/{len(files)}] Açılıyor: {url}")
                write_status(status_path, state="running", current=index, current_file=file_path)
                append_event(status_path, f"{index}/{len(files)} hazırlanıyor: {Path(file_path).name}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                wait_for_steam_login(page)

                if js_snippet:
                    try:
                        page.evaluate(js_snippet)
                        log("Console snippet çalıştırıldı.")
                        append_event(status_path, "Console snippet çalıştırıldı.")
                    except Exception as e:
                        log(f"Console snippet hatası: {e}")
                        append_event(status_path, f"Console snippet hatası: {e}")

                try:
                    page.wait_for_selector("input[type='file']", timeout=60000)
                except PlaywrightTimeoutError:
                    raise RuntimeError("Sayfada dosya input'u bulunamadı. Steam sayfası değişmiş veya giriş tamamlanmamış olabilir.")

                file_input = choose_file_input(page)
                if file_input is None:
                    raise RuntimeError("Dosya input'u bulunamadı.")

                file_input.set_input_files(file_path)
                log(f"Dosya seçildi: {file_path}")
                append_event(status_path, f"Dosya seçildi: {Path(file_path).name}")
                page.wait_for_timeout(wait_after_ms)

                title = render_title(title_template, file_path, index)
                title_selector = fill_title(page, title)
                if title_selector:
                    visible_title = title if title.strip() else "(görünmez karakter)"
                    log(f"Başlık yazıldı: {visible_title}")
                    append_event(status_path, f"Başlık yazıldı: {visible_title}")
                else:
                    log("Başlık alanı bulunamadı.")
                    append_event(status_path, "Başlık alanı bulunamadı.")

                boxes = check_required_boxes(page)
                if boxes:
                    log(f"{len(boxes)} checkbox işaretlendi.")
                    append_event(status_path, f"{len(boxes)} checkbox işaretlendi.")

                if auto_submit:
                    old_url = page.url
                    clicked = click_submit(page)
                    if clicked:
                        log(f"Submit tıklandı: {clicked}")
                        append_event(status_path, f"Submit tıklandı: {clicked}")
                        wait_for_upload_result(page, old_url)
                        page.wait_for_timeout(max(wait_after_ms, 2500))
                    else:
                        log("Submit butonu bulunamadı; elle göndermeni bekliyorum.")
                        append_event(status_path, "Submit butonu bulunamadı; elle gönderim bekleniyor.")
                        write_status(status_path, state="waiting", current=index, current_file=file_path)
                        wait_for_manual_success(page)
                else:
                    log("Auto-submit kapalı; başlığı/checkboxları kontrol edip elle gönder.")
                    write_status(status_path, state="waiting", current=index, current_file=file_path)
                    wait_for_manual_success(page)

                current_status = {}
                try:
                    with open(status_path, "r", encoding="utf-8") as f:
                        current_status = json.load(f)
                except Exception:
                    pass
                completed = current_status.get("completed", [])
                completed.append(file_path)
                write_status(status_path, state="running", completed=completed)
                append_event(status_path, f"{index}/{len(files)} yüklendi: {Path(file_path).name}")
            except Exception as e:
                current_status = {}
                try:
                    with open(status_path, "r", encoding="utf-8") as f:
                        current_status = json.load(f)
                except Exception:
                    pass
                failed = current_status.get("failed", [])
                failed.append({"path": file_path, "error": str(e)})
                write_status(status_path, state="failed", current=index, current_file=file_path, failed=failed, error=str(e))
                append_event(status_path, f"Hata: {Path(file_path).name} | {e}")
                raise

        log("Otomasyon tamamlandı. Tarayıcıyı kapatabilirsin.")
        write_status(status_path, state="done", current=len(files), current_file="")
        append_event(status_path, "Tüm parçalar tamamlandı.")
        context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    run_upload(args.manifest)


if __name__ == "__main__":
    main()
