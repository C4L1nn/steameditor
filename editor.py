import os
import sys
import json
import time
import subprocess
import platform
import threading
import webbrowser
import shutil
import urllib.parse
import urllib.request
import urllib.error

# customtkinter otomatik kurulum
try:
    import customtkinter as ctk
except ImportError:
    print("[SETUP] customtkinter kuruluyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from tkinter import filedialog, messagebox, colorchooser, Text, Toplevel, Canvas, BooleanVar, StringVar, Menu
from tkinter import ttk
from PIL import Image, ImageTk, ImageSequence, ImageDraw, ImageFilter

# Sürükle-bırak desteği (tkinterdnd2 import edilince tüm widget'lara
# drop_target_register/dnd_bind metodlarını ekler; kökte bir kez _require gerekir)
try:
    import tkinterdnd2
    from tkinterdnd2 import DND_FILES
    _DND_AVAILABLE = True
except Exception:
    tkinterdnd2 = None
    DND_FILES = "*"
    _DND_AVAILABLE = False


from applog import get_logger

_log = get_logger("editor")

from core import (
    GIFSICLE_PATH,
    _BORDER_DIR,
    _NO_WINDOW,
    _TEXT_OVERLAY_POSITIONS,
    _border_cfg_enabled,
    _load_gif_frames,
    _parse_hex_color,
    _save_animated_gif,
    _template_preview_canvas,
    _apply_effects_pipeline,
    autocrop_borders,
    find_gifsicle,
    list_border_templates,
    open_folder,
    optimize_gif_file,
    patch_gif_trailing_byte,
    patch_png_last_byte,
    process_folder,
    process_image,
    apply_text_overlay,
    render_showcase_preview,
    render_template_preview,
    resize_cover,
    save_output_piece,
    text_overlay_bbox,
    split_gif_frames,
    template_output_summary,
    uniform_slice_bounds,
)

from config import (
    PROFILE_KEYS,
    TEMPLATES,
    append_history,
    clear_recovery,
    load_recovery,
    save_recovery,
    build_steam_upload_manifest,
    load_config,
    load_custom_presets,
    load_profiles,
    load_projects,
    save_config,
    save_custom_presets,
    save_profiles,
    save_projects,
    upload_status_path,
)

from ui_theme import (
    C_ACCENT, C_ACC_DIM, C_ACC_DK, C_ACC_LT, C_BG0, C_BG1, C_BG2, C_BG3,
    C_BG4, C_BG5, C_BORDER, C_CARD_SEL, C_DIM, C_ERROR, C_HINT, C_INDIGO,
    C_SUCCESS, C_SUCC_DK, C_TEXT,
    AnimButton, lerp, make_ctk_image, _h2r, _r2h,
)
from ui_settings import SettingsPage

F12_ARMED = False  # tek seferlik F12 tetikçisi


def manual_crop_with_template(master, img_path: str, outdir: str, template: dict,
                              cfg: dict | None = None, band_count: int = 1,
                              preset_origin: tuple[int, int] | None = None,
                              region_scale: float = 1.0):
    """
    Manuel crop modu:
    - Kullanıcı sadece İLK bandın İLK parçasının alanını (başlangıç
      pozisyonunu) seçer — tıpkı ezgif'te elle yaptığı gibi.
    - Diğer parçalar aynı bant içinde şablon genişliklerine göre sağa
      doğru otomatik kesilir.
    - `band_count` > 1 ve şablon 'uniform' ise, seçilen başlangıç konumundan
      aşağıya doğru (her biri template height kadar) toplam band_count adet
      bağımsız bant daha otomatik üretilir (kaynağın boyu yetmediği yerde
      sessizce durur, kısmi/gerilmiş bant üretilmez).
    - `preset_origin` verilirse dialog HİÇ açılmaz — konum ana önizlemedeki
      sürüklenebilir grid'den gelir (bkz. App._setup_interactive_preview);
      bu yol saf PIL olduğundan worker thread'de de çağrılabilir.
    """
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(img_path))[0]
    prefix = template.get("prefix", "parca")
    mode = template["mode"]

    # GIF ise burada animasyonlu işlemek istemiyoruz, uyarı verip çıkalım
    if img_path.lower().endswith(".gif"):
        messagebox.showinfo("Bilgi", "Manuel crop şu an sadece statik görsellerde aktif. GIF için otomatik bölme kullan.")
        return []

    # Tüm parçaları tek listede tut — genişlikler uniform_slice_bounds'tan
    # (754/5 -> 151,151,151,151,150; kalan px İLK parçalara dağıtılır)
    if mode == "uniform":
        ph = template["height"]  # sabit — otomatik Böl ile tutarlı (cover-crop)
        parts_info = [{"width": x2 - x1, "height": ph}
                      for x1, x2 in uniform_slice_bounds(template["width"], template["parts"])]
        band_h = template["height"]
    else:
        # Çoklu bant kavramı sadece 'uniform' (eşit parçalı) şablonlarda
        # anlamlı; diğer modlarda tek bant gibi davran.
        band_count = 1
        band_h = 0
        if mode == "multi":
            parts_info = template["parts"]
        else:  # single
            parts_info = [{"width": template["width"], "height": template["height"]}]

    img = Image.open(img_path).convert("RGBA")
    img = autocrop_borders(img, cfg)
    img = _apply_effects_pipeline(img, cfg)
    img_w, img_h = img.size

    # Sadece ilk bandın ilk parçası için kullanıcıdan seçim al
    first = parts_info[0]
    tw = first["width"]
    th = first["height"]
    if preset_origin is not None and mode == "uniform":
        # İnteraktif grid yolu: seçilen bölge (region_scale ile büyütülmüş/
        # küçültülmüş olabilir) TEK seferde kırpılır, şablonun gerçek
        # boyutuna ölçeklenir ve dilimlere ayrılır. rs=1.0'da resize no-op.
        rs = max(0.05, float(region_scale))
        tw_total = template["width"]
        bands_eff = max(1, band_count)
        gw = int(round(tw_total * rs))
        gh = int(round(band_h * bands_eff * rs))
        bx = max(0, min(img_w - gw, int(preset_origin[0])))
        by = max(0, min(img_h - gh, int(preset_origin[1])))
        region = img.crop((bx, by, bx + gw, by + gh))
        target_size = (tw_total, band_h * bands_eff)
        if region.size != target_size:
            region = region.resize(target_size, Image.LANCZOS)

        created = []
        idx = 1
        for band in range(bands_eff):
            y1 = band * band_h
            for x1, x2 in uniform_slice_bounds(tw_total, len(parts_info)):
                piece = region.crop((x1, y1, x2, y1 + band_h))
                full = save_output_piece(piece, outdir, f"{prefix}_{base}_{idx:02}",
                                         cfg, bool(template.get("patch")))
                created.append(full)
                idx += 1
        return created

    if preset_origin is not None:
        base_x = max(0, min(img_w - tw, int(preset_origin[0])))
        base_y = max(0, min(img_h - th, int(preset_origin[1])))
    else:
        if band_count > 1:
            title = (f"Başlangıç (1. Bant) - {tw}x{th} alanını seç — aşağıya doğru "
                     f"{band_count} bant otomatik devam edecek (ENTER ile onayla)")
        else:
            title = f"Başlangıç - {tw}x{th} alanını seç (ENTER ile onayla)"
        dlg = FixedCropDialog(master, img, tw, th, title=title)
        bbox = dlg.get_bbox()
        if not bbox:
            return []
        x1, y1, x2, y2 = bbox
        base_x = x1
        base_y = y1

    created = []
    idx = 1

    for band in range(max(1, band_count)):
        band_y = base_y + band * band_h
        # Otomatik devam eden bantlar (ilk banttan sonrakiler) kaynağa tam
        # sığmıyorsa kısmi/gerilmiş bant üretmeden sessizce dur.
        if band > 0 and band_y + band_h > img_h:
            break

        cur_x = base_x
        for part in parts_info:
            pw = part["width"]
            ph = part["height"]

            px1 = cur_x
            py1 = band_y

            # Taşma kontrolü (sağ kenar / alt kenar) — sadece ilk bant için,
            # kullanıcının kendi seçtiği konumu makul ölçüde tolere eder.
            if px1 + pw > img_w:
                px1 = max(0, img_w - pw)
            if py1 + ph > img_h:
                py1 = max(0, img_h - ph)

            px2 = px1 + pw
            py2 = py1 + ph

            piece = img.crop((px1, py1, px2, py2))
            full = save_output_piece(piece, outdir, f"{prefix}_{base}_{idx:02}",
                                     cfg, bool(template.get("patch")))
            created.append(full)
            idx += 1
            cur_x += pw  # sonraki parçayı sağa kaydır

    return created


# ==========================================================
#   GUI — Carbon × Steam Turuncu (customtkinter)
# ==========================================================


# ── TemplateCard ────────────────────────────────────────────
class TemplateCard(ctk.CTkFrame):
    """Seçilince turuncu kenarlıkla parlayan şablon kartı."""
    _N = 10; _MS = 12

    def __init__(self, master, template, on_select, **kw):
        kw.setdefault("corner_radius", 10)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=C_BG3,
                         border_color=C_BORDER, **kw)
        self.tmpl = template
        self._on_select = on_select
        self._selected = False
        self._t = 0.0
        self._aid = None

        # İkon + isim
        icons = {"uniform": "⚡", "multi": "✏️", "single": "🖼"}
        icon = icons.get(template.get("mode", "uniform"), "◆")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=11, pady=(10, 2))

        ctk.CTkLabel(top, text=icon, font=ctk.CTkFont("Segoe UI Emoji", 16),
                     text_color=C_ACCENT, width=22).pack(side="left", anchor="n")
        ctk.CTkLabel(top, text=template["name"],
                     font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                     text_color=C_TEXT, wraplength=138,
                     justify="left").pack(side="left", padx=(7, 0), anchor="n")

        # Alt bilgi
        info = self._info_text(template)
        ctk.CTkLabel(self, text=info,
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C_DIM, justify="left",
                     wraplength=176).pack(anchor="w", padx=14, pady=(0, 9))

        # Tıklama alanı
        for w in (self, *self.winfo_children()):
            try:
                w.bind("<Button-1>", self._click, add="+")
                w.bind("<Enter>",    self._hover, add="+")
                w.bind("<Leave>",    self._unhover, add="+")
            except Exception:
                pass

    def _info_text(self, t):
        m = t.get("mode")
        if m == "uniform":
            bounds = uniform_slice_bounds(t["width"], t["parts"])
            pw = bounds[0][1] - bounds[0][0]
            base = f"{t['parts']} parça · {pw}px × {t.get('height', '?')}px"
            return base + ("  ·  Patch ✓" if t.get("patch") else "")
        if m == "multi":
            parts = t.get("parts", [])
            widths = " + ".join(f"{p['width']}px" for p in parts)
            max_h = max((p["height"] for p in parts), default=0)
            return f"{widths} · {len(parts)} parça · {max_h}px yüksek"
        if m == "single":
            return f"{t.get('width',650)}×{t.get('height',850)}px · tek parça"
        return ""

    def _click(self, _=None):
        self._on_select(self.tmpl)

    def _hover(self, _=None):
        if not self._selected:
            self.configure(fg_color=C_BG4)

    def _unhover(self, _=None):
        if not self._selected:
            self.configure(fg_color=C_BG3)

    def set_selected(self, val: bool):
        self._selected = val
        target = 1.0 if val else 0.0
        if self._aid:
            try: self.after_cancel(self._aid)
            except: pass
        delta = (target - self._t) / self._N
        def tick(n=self._N):
            self._t = max(0.0, min(1.0, self._t + delta))
            bc = lerp(C_BORDER, C_ACCENT, self._t)
            bg = lerp(C_BG3, C_CARD_SEL, self._t)
            try:
                self.configure(border_color=bc, fg_color=bg)
            except: return
            if n > 1:
                self._aid = self.after(self._MS, tick, n-1)
            else:
                self._t = target
        tick()


# ── DropZone ────────────────────────────────────────────────
class DropZone(ctk.CTkFrame):
    """Dosya bırakma / önizleme alanı."""
    _PULSE_STEPS = 40

    def __init__(self, master, on_file, on_batch=None, initialdir_getter=None, **kw):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=C_BG2,
                         border_color=C_BORDER, **kw)
        self._on_file = on_file
        self._on_batch = on_batch
        self._initialdir_getter = initialdir_getter
        self._pulse_id = None
        self._pulse_t = 0.0
        self._pulse_dir = 1

        # İçerik — boş hal
        self._idle_frame = ctk.CTkFrame(self, fg_color="transparent")

        badge = ctk.CTkFrame(self._idle_frame, width=86, height=86,
                             corner_radius=43, fg_color=C_BG3)
        badge.pack(pady=(10, 16))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="📂",
                     font=ctk.CTkFont("Segoe UI Emoji", 36),
                     text_color=C_ACC_LT).pack(expand=True)

        ctk.CTkLabel(self._idle_frame,
                     text="Görseli buraya sürükle",
                     font=ctk.CTkFont("Segoe UI", 17, weight="bold"),
                     text_color=C_TEXT).pack()
        ctk.CTkLabel(self._idle_frame,
                     text="veya tıklayıp dosya seç",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=C_DIM).pack(pady=(3, 16))

        pill = ctk.CTkFrame(self._idle_frame, fg_color=C_BG3, corner_radius=12)
        pill.pack()
        ctk.CTkLabel(pill, text="PNG    ·    JPG    ·    WEBP    ·    GIF",
                     font=ctk.CTkFont("Segoe UI", 10, weight="bold"),
                     text_color=C_DIM).pack(padx=16, pady=6)

        # Keşfedilebilirlik: gizli etkileşimlerin özeti (sadece boş halde
        # görünür — görsel yüklenince kaybolur, akışı hiç kalabalıklaştırmaz)
        tips = ctk.CTkFrame(self._idle_frame, fg_color="transparent")
        tips.pack(pady=(22, 0))
        ctk.CTkLabel(tips, text="İPUÇLARI",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_HINT).pack()
        for line in (
            "🖱  Bölme grid'ini sürükle · köşesinden büyüt/küçült",
            "🖱  Çift tık = Böl   ·   Sağ tık = hizalama menüsü",
            "✏  Metin katmanını önizlemede sürükleyerek yerleştir",
            "🎮  Canlı vitrin: bant sayısının yanındaki buton",
            "⌨  Ctrl+O aç   ·   Ctrl+Enter böl   ·   Esc geri",
        ):
            ctk.CTkLabel(tips, text=line,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(pady=1)

        self._idle_frame.pack(expand=True)

        # Preview label
        self._preview_label = ctk.CTkLabel(self, text="",
                                           fg_color="transparent")
        self._preview_info = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            text_color=C_ACCENT,
            fg_color=C_BG3,
            corner_radius=8,
            padx=10,
            pady=5)

        # Toplu seçim rozeti (birden fazla dosya seçilince görselin üstünde durur)
        self._batch_badge = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            text_color=C_BG0,
            fg_color=C_ACCENT,
            corner_radius=10,
            padx=10,
            pady=4)

        self.bind("<Button-1>", self._pick, add="+")

        def _bind_click(w):
            try:
                w.bind("<Button-1>", self._pick, add="+")
            except Exception:
                pass
            for c in w.winfo_children():
                _bind_click(c)
        _bind_click(self._idle_frame)

        # Drag & drop (kök pencerede tkdnd yüklüyse çalışır)
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

        self._start_pulse()

    def _start_pulse(self):
        def tick():
            self._pulse_t += 0.025 * self._pulse_dir
            if self._pulse_t >= 1.0:
                self._pulse_t = 1.0; self._pulse_dir = -1
            elif self._pulse_t <= 0.0:
                self._pulse_t = 0.0; self._pulse_dir = 1
            try:
                bc = lerp(C_BORDER, C_HINT, self._pulse_t)
                self.configure(border_color=bc)
            except: return
            self._pulse_id = self.after(50, tick)
        tick()

    def _stop_pulse(self):
        if self._pulse_id:
            try: self.after_cancel(self._pulse_id)
            except: pass

    def _pick(self, _=None):
        kwargs = {"filetypes": [("Resimler", "*.png;*.jpg;*.jpeg;*.webp;*.gif")]}
        d = self._initialdir_getter() if self._initialdir_getter else ""
        if d and os.path.isdir(d):
            kwargs["initialdir"] = d
        paths = filedialog.askopenfilenames(**kwargs)
        if not paths:
            return
        if len(paths) == 1:
            self._on_file(paths[0])
        elif self._on_batch:
            self._on_batch(list(paths))

    def _on_drop(self, event):
        # event.data: boşluklu yollar {..} ile sarılı, çoklu dosya boşlukla ayrık
        try:
            raw = self.tk.splitlist(event.data)
        except Exception:
            raw = [event.data]
        paths = []
        for path in raw:
            path = path.strip().strip("{}")
            if os.path.isfile(path) or os.path.isdir(path):
                paths.append(path)
        if not paths:
            return
        files_only = [p for p in paths if os.path.isfile(p)]
        if len(files_only) > 1 and self._on_batch:
            self._on_batch(files_only)
        else:
            self._on_file(paths[0])

    def bind_preview_mouse(self, on_press, on_drag, on_release=None,
                           on_double=None, on_context=None, on_wheel=None):
        """Önizleme görselinin üstünde fare desteği (grid/metin taşıma,
        çift tık = böl, sağ tık = hizalama menüsü, tekerlek = zoom). Boş
        (idle) alandaki tıklama davranışı değişmez — sadece görsel
        gösterilirken aktif olan label'a bağlanır."""
        self._preview_label.configure(cursor="fleur")
        self._preview_label.bind("<ButtonPress-1>", on_press, add="+")
        self._preview_label.bind("<B1-Motion>", on_drag, add="+")
        if on_release:
            self._preview_label.bind("<ButtonRelease-1>", on_release, add="+")
        if on_double:
            self._preview_label.bind("<Double-Button-1>", on_double, add="+")
        if on_context:
            self._preview_label.bind("<Button-3>", on_context, add="+")
        if on_wheel:
            self._preview_label.bind("<MouseWheel>", on_wheel, add="+")

    def show_image(self, img: Image.Image, info: str = "", batch_count: int = 0):
        self._stop_pulse()
        self._idle_frame.pack_forget()

        w = max(self.winfo_width(), 700)
        h = max(self.winfo_height(), 480)
        thumb = img.copy()
        thumb.thumbnail((max(1, w - 24), max(1, h - 24)), Image.LANCZOS)
        ctk_img = make_ctk_image(thumb)

        self._preview_label.configure(image=ctk_img, text="")
        self._preview_label._image = ctk_img
        self._preview_label.pack(expand=True)
        if info:
            self._preview_info.configure(text=info)
            self._preview_info.pack(pady=(0, 10))
        else:
            self._preview_info.pack_forget()
        if batch_count > 1:
            self._batch_badge.configure(text=f"🗂  +{batch_count - 1} dosya daha (toplu)")
            self._batch_badge.place(relx=1.0, rely=0.0, anchor="ne", x=-14, y=14)
        else:
            self._batch_badge.place_forget()
        self.configure(border_color=C_ACCENT)

    def reset(self):
        self._preview_label.pack_forget()
        self._preview_info.pack_forget()
        self._batch_badge.place_forget()
        self._idle_frame.pack(expand=True)
        self.configure(border_color=C_BORDER)
        self._pulse_t = 0.0; self._pulse_dir = 1
        self._start_pulse()


# ── StatusBar ───────────────────────────────────────────────
class StatusBar(ctk.CTkFrame):
    """Alt durum çubuğu — animasyonlu mesaj gösterimi."""

    def __init__(self, master, **kw):
        kw.setdefault("corner_radius", 8)
        super().__init__(master, fg_color=C_BG2, height=36, **kw)
        self.pack_propagate(False)

        self._dot = ctk.CTkLabel(self, text="●",
                                 font=ctk.CTkFont("Segoe UI", 11),
                                 text_color=C_SUCCESS, width=20)
        self._dot.pack(side="left", padx=(12, 4))

        self._lbl = ctk.CTkLabel(self, text="Hazır",
                                 font=ctk.CTkFont("Segoe UI", 11),
                                 text_color=C_DIM, anchor="w")
        self._lbl.pack(side="left", fill="x", expand=True)

        self._right = ctk.CTkLabel(self, text="",
                                   font=ctk.CTkFont("Consolas", 9),
                                   text_color=C_HINT)
        self._right.pack(side="right", padx=12)

        self._fade_id = None

    def set(self, msg: str, color=C_TEXT, dot=C_SUCCESS, auto_reset=True):
        if self._fade_id:
            try: self.after_cancel(self._fade_id)
            except: pass
        self._dot.configure(text_color=dot)
        self._lbl.configure(text=msg, text_color=color)
        if auto_reset:
            self._fade_id = self.after(4000, self._fade_to_ready)

    def set_right(self, txt: str):
        self._right.configure(text=txt)

    def _fade_to_ready(self):
        self._lbl.configure(text="Hazır", text_color=C_DIM)
        self._dot.configure(text_color=C_SUCCESS)

    def busy(self, msg="İşleniyor..."):
        self.set(msg, C_ACCENT, C_ACCENT, auto_reset=False)

    def ok(self, msg):
        self.set(msg, C_SUCCESS, C_SUCCESS)

    def error(self, msg):
        self.set(msg, C_ERROR, C_ERROR)


# ── SplitPreview ────────────────────────────────────────────
class SplitPreview(ctk.CTkFrame):
    """
    Bölme sonrası parçaları yan yana gösteren önizleme paneli.
    Üstte başlık + 'Geri' butonu, altta yatay kaydırılabilir thumbnail şeridi.
    """
    _THUMB_W = 130
    _THUMB_H = 180

    def __init__(self, master, on_back, on_open, on_rerun, on_clear,
                 on_open_file, on_copy_path, on_delete_file, on_upload=None, **kw):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=C_BG2,
                         border_color=C_ACCENT, **kw)
        self._on_upload = on_upload
        self._on_back = on_back
        self._on_open = on_open
        self._on_rerun = on_rerun
        self._on_clear = on_clear
        self._on_open_file = on_open_file
        self._on_copy_path = on_copy_path
        self._on_delete_file = on_delete_file
        self._tk_imgs = []   # referansları tut, GC'e gitmesin
        self._file_paths = []

        # Üst başlık çubuğu
        hdr = ctk.CTkFrame(self, fg_color=C_BG3, corner_radius=0,
                           height=40)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self._title_lbl = ctk.CTkLabel(
            hdr, text="",
            font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
            text_color=C_ACCENT)
        self._title_lbl.pack(side="left", padx=14)

        AnimButton(hdr, text="← Geri",
                   nc=C_BG3, hc=C_BG4,
                   height=28, corner_radius=6,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_DIM,
                   command=self._on_back
                   ).pack(side="right", padx=10, pady=6)

        AnimButton(hdr, text="Klasörde Aç",
                   nc=C_BG3, hc=C_BG4,
                   height=28, corner_radius=6,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=self._on_open
                   ).pack(side="right", padx=(0, 6), pady=6)

        AnimButton(hdr, text="Yeniden İşle",
                   nc=C_BG3, hc=C_BG4,
                   height=28, corner_radius=6,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_ACCENT,
                   command=self._on_rerun
                   ).pack(side="right", padx=(0, 6), pady=6)

        AnimButton(hdr, text="Son Çıktıyı Temizle",
                   nc=C_BG3, hc=C_BG4,
                   height=28, corner_radius=6,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_ERROR,
                   command=self._clear_current
                   ).pack(side="right", padx=(0, 6), pady=6)

        # Akış kısayolu: bölme sonrası tek tıkla upload — sidebar'a gitmeye
        # gerek kalmaz (böl -> kontrol et -> yükle akışı tek panelde biter).
        if self._on_upload:
            AnimButton(hdr, text="☁ Steam'e Yükle",
                       nc=C_ACC_DK, hc=C_ACCENT, variant="accent",
                       height=28, corner_radius=6,
                       font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                       text_color=C_TEXT,
                       command=self._on_upload
                       ).pack(side="right", padx=(0, 6), pady=6)

        # Vitrin/parça görünümü değiştirici — pop-up yerine aynı panelde
        # görünüm değişir (Steam profil vitrini simülasyonu).
        self._view_btn = AnimButton(hdr, text="🎮 Vitrin",
                   nc=C_BG3, hc=C_INDIGO,
                   height=28, corner_radius=6,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=self._toggle_view)
        self._view_btn.pack(side="right", padx=(0, 6), pady=6)

        # Thumbnail şeridi
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            orientation="horizontal",
            scrollbar_button_color=C_BG4,
            scrollbar_button_hover_color=C_ACCENT)
        self._scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Vitrin görünümü (başta gizli) — dikey kaydırılabilir simülasyon
        self._showcase = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=C_BG4,
            scrollbar_button_hover_color=C_ACCENT)
        self._showcase_lbl = ctk.CTkLabel(self._showcase, text="",
                                          fg_color="transparent")
        self._showcase_lbl.pack(pady=4)
        self._showcase_mode = False
        self._parts_per_row = 5

    def _toggle_view(self):
        self._showcase_mode = not self._showcase_mode
        if self._showcase_mode:
            self._scroll.pack_forget()
            self._showcase.pack(fill="both", expand=True, padx=10, pady=10)
            self._view_btn.configure(text="▤ Parçalar")
            self._render_showcase()
        else:
            self._showcase.pack_forget()
            self._scroll.pack(fill="both", expand=True, padx=10, pady=10)
            self._view_btn.configure(text="🎮 Vitrin")

    def _render_showcase(self):
        if not self._file_paths:
            self._showcase_lbl.configure(image=None, text="Gösterilecek parça yok")
            return
        sim = render_showcase_preview(self._file_paths, self._parts_per_row)
        # Panel genişliğine sığdır (en fazla 1:1)
        avail = max(400, self.winfo_width() - 60)
        if sim.width > avail:
            scale = avail / sim.width
            sim = sim.resize((avail, max(1, int(sim.height * scale))), Image.LANCZOS)
        ctk_img = make_ctk_image(sim)
        self._showcase_lbl.configure(image=ctk_img, text="")
        self._showcase_lbl._image = ctk_img

    def load(self, file_paths: list, parts_per_row: int | None = None):
        """Parça dosyalarını yükleyip thumbnail olarak göster."""
        # Önceki içeriği temizle
        for w in self._scroll.winfo_children():
            w.destroy()
        self._tk_imgs.clear()
        self._file_paths = list(file_paths)
        if parts_per_row:
            self._parts_per_row = max(1, int(parts_per_row))

        n = len(file_paths)
        self._title_lbl.configure(
            text=f"✂  {n} parça oluşturuldu")
        if self._showcase_mode:
            self._render_showcase()

        for i, path in enumerate(file_paths):
            card = ctk.CTkFrame(
                self._scroll, fg_color=C_BG3,
                corner_radius=12, width=self._THUMB_W + 22, height=372)
            card.pack(side="left", anchor="n", padx=6, pady=4)
            card.pack_propagate(False)

            # Thumbnail oluştur
            try:
                img = Image.open(path)
                # GIF: n_frames bazı Steam uyumlu olmayan çıktılarda hata verebilir;
                # önizleme için sadece ilk kareyi okumak yeterli.
                if os.path.splitext(path)[1].lower() == ".gif":
                    img.seek(0)
                img = img.convert("RGBA")
                img.thumbnail((self._THUMB_W, self._THUMB_H), Image.LANCZOS)

                # Saydam arka plan → koyu renk
                bg = Image.new("RGBA", img.size, _h2r(C_BG3) + (255,))
                bg.paste(img, mask=img.split()[3])
                ctk_img = make_ctk_image(bg.convert("RGB"))
                self._tk_imgs.append(ctk_img)

                img_lbl = ctk.CTkLabel(card, image=ctk_img, text="",
                                       fg_color="transparent")
                img_lbl.pack(pady=(10, 4))
            except Exception:
                ctk.CTkLabel(card, text="?",
                             font=ctk.CTkFont("Segoe UI", 28),
                             text_color=C_DIM).pack(pady=20)

            # Parça numarası
            ctk.CTkLabel(card,
                         text=f"#{i+1}",
                         font=ctk.CTkFont("Consolas", 11, weight="bold"),
                         text_color=C_ACCENT).pack()

            # Dosya adı (kısa)
            fname = os.path.basename(path)
            short = fname if len(fname) <= 18 else fname[:15] + "…"
            ctk.CTkLabel(card, text=short,
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=C_DIM).pack(pady=(0, 4))

            # Boyut
            try:
                kb = os.path.getsize(path) / 1024
                size_str = f"{kb:.0f} KB" if kb < 1024 else f"{kb/1024:.1f} MB"
            except Exception:
                size_str = ""
            if size_str:
                ctk.CTkLabel(card, text=size_str,
                             font=ctk.CTkFont("Segoe UI", 9),
                             text_color=C_HINT).pack(pady=(0, 8))

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=8, pady=(0, 8))
            for label, cmd in [
                ("Aç", lambda p=path: self._on_open_file(p)),
                ("Kopyala", lambda p=path: self._on_copy_path(p)),
                ("Sil", lambda p=path: self._on_delete_file(p)),
            ]:
                AnimButton(actions, text=label,
                           nc=C_BG4, hc=C_BG5,
                           height=24, corner_radius=6,
                           font=ctk.CTkFont("Segoe UI", 9),
                           text_color=C_ERROR if label == "Sil" else C_TEXT,
                           command=cmd).pack(fill="x", pady=2)

    def _clear_current(self):
        self._on_clear(list(self._file_paths))


# ── FixedCropDialog ─────────────────────────────────────────
class FixedCropDialog(Toplevel):
    """Manuel crop — sabit boyutlu, zoom + pan destekli."""

    def __init__(self, master, image, target_w, target_h, title="Crop"):
        super().__init__(master)
        self.title(title)
        self.configure(bg=C_BG1)
        self.image = image
        self.target_w = target_w
        self.target_h = target_h
        self.scale = 0.5
        self.min_scale = 0.15
        self.max_scale = 4.0
        self.result_bbox = None

        # Kırpma kutusunun konumu ORİJİNAL görsel piksel uzayında tutulur
        # (scale'den bağımsız); böylece zoom (_redraw) kullanıcının
        # sürükleyip bıraktığı yeri unutup merkeze sıçramaz.
        self.box_x = max(0, (image.width - target_w) / 2)
        self.box_y = max(0, (image.height - target_h) / 2)

        self.canvas = Canvas(self, bg=C_BG0, cursor="crosshair",
                             highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.geometry("900x620")

        self.canvas.bind("<MouseWheel>",    self._wheel)
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>",     self._pan_do)
        self.canvas.bind("<Button-1>",      self._click)
        self.bind("<Return>", self._enter)
        self.bind("<Escape>", self._cancel)
        # Ok tuşları: kutuyu orijinal görsel pikselinde 1px (Shift ile 10px)
        # kaydır — ezgif'teki sayısal Left/Top girme hassasiyetinin karşılığı.
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.bind(f"<{key}>", lambda _e, dx=dx, dy=dy: self._nudge(dx, dy))
            self.bind(f"<Shift-{key}>", lambda _e, dx=dx, dy=dy: self._nudge(dx * 10, dy * 10))
        self.focus_force()

        # hint
        hint = ctk.CTkLabel(self, text="Scroll → zoom   |   Orta tık → pan   |   Sol tık → kareyi taşı   |   Ok tuşları → 1px (Shift: 10px)   |   Enter → onayla",
                             font=ctk.CTkFont("Segoe UI", 9),
                             text_color=C_DIM, fg_color=C_BG2)
        hint.pack(fill="x", pady=0)

        tools = ctk.CTkFrame(self, fg_color=C_BG2, corner_radius=0)
        tools.pack(fill="x")
        for label, anchor in [
            ("Sola", "left"),
            ("Ortala", "center"),
            ("Sağa", "right"),
            ("Yukarı", "top"),
            ("Dikey Orta", "middle"),
            ("Aşağı", "bottom"),
        ]:
            AnimButton(tools, text=label,
                       nc=C_BG3, hc=C_BG4,
                       height=26, corner_radius=6,
                       font=ctk.CTkFont("Segoe UI", 10),
                       text_color=C_DIM,
                       command=lambda a=anchor: self._snap(a)
                       ).pack(side="left", padx=4, pady=5)

        self.rect_id = None
        self.tk_img  = None
        self._redraw()

    def _redraw(self):
        w, h = self.image.size
        sw = max(1, int(w * self.scale))
        sh = max(1, int(h * self.scale))
        disp = self.image.resize((sw, sh), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.configure(scrollregion=(0, 0, sw, sh))
        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1 = max(0, min(sw - tw, self.box_x * self.scale))
        y1 = max(0, min(sh - th, self.box_y * self.scale))
        # Gölge efekti
        self.canvas.create_rectangle(
            x1+2, y1+2, x1+tw+2, y1+th+2,
            outline="", fill="#050505")
        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x1+tw, y1+th,
            outline=C_ACCENT, width=2,
            dash=(6, 3))

    def _wheel(self, e):
        delta = 0.12 if e.delta > 0 else -0.12
        ns = min(self.max_scale, max(self.min_scale, self.scale + delta))
        if abs(ns - self.scale) < 0.01: return
        cx = self.canvas.canvasx(e.x) / (self.image.width * self.scale)
        cy = self.canvas.canvasy(e.y) / (self.image.height * self.scale)
        self.scale = ns
        self._redraw()
        sw = self.image.width  * ns
        sh = self.image.height * ns
        self.canvas.xview_moveto((cx * sw - e.x) / sw)
        self.canvas.yview_moveto((cy * sh - e.y) / sh)

    def _pan_start(self, e): self.canvas.scan_mark(e.x, e.y)
    def _pan_do(self, e):    self.canvas.scan_dragto(e.x, e.y, gain=1)

    def _click(self, e):
        if not self.rect_id: return
        cx = self.canvas.canvasx(e.x)
        cy = self.canvas.canvasy(e.y)
        sw = self.image.width  * self.scale
        sh = self.image.height * self.scale
        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1 = max(0, min(sw - tw, cx - tw/2))
        y1 = max(0, min(sh - th, cy - th/2))
        self.canvas.coords(self.rect_id, x1, y1, x1+tw, y1+th)
        self.box_x = x1 / self.scale
        self.box_y = y1 / self.scale

    def _nudge(self, dx: int, dy: int):
        """Kutuyu orijinal görsel piksel uzayında dx/dy kadar kaydırır."""
        if not self.rect_id:
            return
        sw = self.image.width * self.scale
        sh = self.image.height * self.scale
        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1 = max(0.0, min(sw - tw, (self.box_x + dx) * self.scale))
        y1 = max(0.0, min(sh - th, (self.box_y + dy) * self.scale))
        self.canvas.coords(self.rect_id, x1, y1, x1 + tw, y1 + th)
        self.box_x = x1 / self.scale
        self.box_y = y1 / self.scale

    def _snap(self, anchor):
        if not self.rect_id:
            return
        sw = self.image.width * self.scale
        sh = self.image.height * self.scale
        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1, y1, _, _ = self.canvas.coords(self.rect_id)
        if anchor == "left":
            x1 = 0
        elif anchor == "center":
            x1 = max(0, (sw - tw) / 2)
        elif anchor == "right":
            x1 = max(0, sw - tw)
        elif anchor == "top":
            y1 = 0
        elif anchor == "middle":
            y1 = max(0, (sh - th) / 2)
        elif anchor == "bottom":
            y1 = max(0, sh - th)
        self.canvas.coords(self.rect_id, x1, y1, x1 + tw, y1 + th)
        self.box_x = x1 / self.scale
        self.box_y = y1 / self.scale

    def _enter(self, _=None):
        if self.rect_id:
            x1, y1, x2, y2 = self.canvas.coords(self.rect_id)
            ix1 = int(x1 / self.scale)
            iy1 = int(y1 / self.scale)
            w, h = self.image.size
            ix1 = max(0, min(w - self.target_w, ix1))
            iy1 = max(0, min(h - self.target_h, iy1))
            self.result_bbox = (ix1, iy1, ix1 + self.target_w, iy1 + self.target_h)
        self.destroy()

    def _cancel(self, _=None):
        self.result_bbox = None
        self.destroy()

    def get_bbox(self):
        self.wait_window()
        return self.result_bbox


# ── App ─────────────────────────────────────────────────────
class App(ctk.CTk):

    def __init__(self, preload_path=None):
        super().__init__()
        # Sürükle-bırak için tkdnd Tcl uzantısını köke yükle
        self._dnd_ok = False
        if _DND_AVAILABLE:
            try:
                tkinterdnd2.TkinterDnD._require(self)
                self._dnd_ok = True
            except Exception as e:
                _log.warning(f"[DND] tkdnd yüklenemedi, sürükle-bırak devre dışı: {e}")
        self.title("SplitForge — Steam Showcase Studio")
        self.geometry("1340x840")
        self.minsize(1040, 700)
        self.configure(fg_color=C_BG1)
        self._apply_app_icon()

        self.current_path = None
        self._batch_files = None         # çoklu seçim: belirli dosya listesi (klasörden ayrı)
        self._grid_pos = None            # sürüklenebilir bölme grid'inin konumu (orijinal px)
        self._grid_scale = 1.0           # grid bölge ölçeği (köşeden büyüt/küçült)
        self._live_showcase = False      # sürüklerken köşede canlı vitrin PiP'i
        self._pv = None                  # interaktif önizleme cache'i (ölçekli taban vs.)
        self._last_outputs = []
        self._splitting = False          # async bölme sırasında tekrar tetiklemeyi engelle
        self._upload_proc = None         # çalışan Community uploader süreç tutamacı
        self.template = TEMPLATES[0]
        self._cfg = load_config()
        saved_out = self._cfg.get("output_dir", "")
        _default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        self.output_dir = saved_out if saved_out and os.path.isdir(saved_out) \
                          else _default_out
        default_name = self._cfg.get("default_preset", "")
        for t in TEMPLATES:
            if t["name"] == default_name:
                self.template = t
                break

        self._build()

        # Klavye kısayolları: Ctrl+O dosya seç, Ctrl+Enter böl, Esc geri
        self.bind("<Control-o>", lambda _e: self._pick_file())
        self.bind("<Control-Return>", lambda _e: self._split_single())
        self.bind("<Escape>", self._on_escape)

        # Kilitlenme kurtarma: temiz kapanışta dosya silinir; açılışta hâlâ
        # duruyorsa son oturum çökmüş demektir -> devam etmek iste.
        self._last_recovery_state = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(30000, self._recovery_tick)

        if preload_path and os.path.isfile(preload_path):
            # Pencere tam çizilmeden önizleme boyutlandırması yanlış çıkmasın diye
            # mainloop başladıktan sonraya ertele.
            self.after(200, lambda: self._on_file_drop(preload_path))
        else:
            self.after(400, self._offer_recovery)

    def _apply_app_icon(self):
        """Pencere/görev çubuğu ikonunu (app_icon.ico) ve sidebar logosunu
        (app_icon.png) ayarlar. Dosya yoksa sessizce ✂ glifine düşer."""
        root = os.path.dirname(os.path.abspath(__file__))
        ico = os.path.join(root, "app_icon.ico")
        png = os.path.join(root, "app_icon.png")
        if os.path.isfile(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass
        if os.path.isfile(png):
            try:
                self._icon_photo = ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_photo)
                self._logo_img = make_ctk_image(Image.open(png).resize((34, 34), Image.LANCZOS))
            except Exception:
                self._logo_img = None

    # ──────────────────────────────────────────────────────
    def _build(self):
        # Ana grid: sidebar | içerik
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_settings_page()

    def _build_settings_page(self):
        """Ayarlar/Border FX/Şablonlar/Steam API/Notlar için tek sayfa.
        main ile aynı hücrede durur; ikisinden sadece biri görünür olur."""
        self._settings_page = SettingsPage(self, self, self._close_settings_page)
        self._settings_page.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self._settings_page.grid_remove()

    def _open_settings_page(self, tab="Genel"):
        self._main.grid_remove()
        self._settings_page.grid()
        self._settings_page.open_tab(tab)

    def _close_settings_page(self):
        self._settings_page.grid_remove()
        self._main.grid()

    # ── Kilitlenme kurtarma ───────────────────────────────
    def _recovery_snapshot(self) -> dict | None:
        """Kurtarılmaya değer bir çalışma durumu varsa sözlük döner."""
        if not self.current_path and not self._batch_files:
            return None
        state = {"template_name": self.template.get("name"),
                 "timestamp": time.time()}
        if self._batch_files:
            state["input_paths"] = list(self._batch_files)
        elif os.path.isdir(self.current_path):
            state["input_dir"] = self.current_path
        else:
            state["input_paths"] = [self.current_path]
        return state

    def _recovery_tick(self):
        try:
            state = self._recovery_snapshot()
            if state is not None:
                # timestamp hariç değişiklik yoksa diske yazma
                comparable = {k: v for k, v in state.items() if k != "timestamp"}
                if comparable != self._last_recovery_state:
                    save_recovery(state)
                    self._last_recovery_state = comparable
        except Exception as e:
            _log.error(f"[RECOVERY TICK ERR] {e}")
        self.after(30000, self._recovery_tick)

    def _offer_recovery(self):
        state = load_recovery()
        if not state:
            return
        paths = state.get("input_paths") or []
        input_dir = state.get("input_dir", "")
        valid_paths = [p for p in paths if os.path.isfile(p)]
        if not valid_paths and not (input_dir and os.path.isdir(input_dir)):
            clear_recovery()
            return
        desc = (os.path.basename(input_dir) + " (klasör)") if input_dir else (
            os.path.basename(valid_paths[0]) + (f" +{len(valid_paths) - 1} dosya" if len(valid_paths) > 1 else ""))
        if not messagebox.askyesno(
                "Kaldığın Yerden Devam",
                f"Son oturum düzgün kapanmamış görünüyor.\n\n"
                f"Üzerinde çalıştığın iş geri yüklensin mi?\n• {desc}"):
            clear_recovery()
            return
        tmpl = next((t for t in TEMPLATES if t["name"] == state.get("template_name")), None)
        if tmpl:
            self.template = tmpl
            self._sync_cards()
            self._status.set_right(tmpl["name"])
        if input_dir and os.path.isdir(input_dir):
            self._on_file_drop(input_dir)
        elif len(valid_paths) > 1:
            self._on_batch_drop(valid_paths)
        else:
            self._on_file_drop(valid_paths[0])
        self._status.ok("Çalışma geri yüklendi ✓")

    def _on_close(self):
        clear_recovery()  # temiz kapanış — kurtarmaya gerek yok
        self.destroy()

    def _on_escape(self, _=None):
        """Esc: ayarlar sayfası açıksa ona, değilse split önizlemeden drop'a dön.
        grid_info() kullanılır (grid_remove sonrası boş döner) — winfo_ismapped
        pencere simge durumundayken/gizliyken her zaman 0 döndüğü için yanıltıcı."""
        if self._settings_page.grid_info():
            self._settings_page._back()
        elif self._split_prev.grid_info():
            self._back_to_drop()

    def _notify_attention(self):
        """Uzun bir iş bitince ses + görev çubuğunda yanıp sönme.
        Bağımlılıksız (winsound + user32.FlashWindow); pencere zaten
        öndeyse sadece ses duyulur."""
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            try:
                self.bell()
            except Exception:
                pass
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2)  # GA_ROOT
            ctypes.windll.user32.FlashWindow(hwnd, True)
        except Exception:
            pass

    # ── SIDEBAR ───────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=260, fg_color=C_BG2,
                          corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(1, weight=1)  # kaydırılabilir gövde tüm boşluğu alır

        # Logo — sabit, kaymaz. Uygulama ikonu varsa onu, yoksa ✂ glifini göster.
        logo_f = ctk.CTkFrame(sb, fg_color="transparent")
        logo_f.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 4))
        logo_img = getattr(self, "_logo_img", None)
        if logo_img is not None:
            ctk.CTkLabel(logo_f, text="", image=logo_img).pack(side="left")
        else:
            ctk.CTkLabel(logo_f, text="✂",
                         font=ctk.CTkFont("Segoe UI Symbol", 26),
                         text_color=C_ACCENT).pack(side="left")
        name_f = ctk.CTkFrame(logo_f, fg_color="transparent")
        name_f.pack(side="left", padx=8)
        ctk.CTkLabel(name_f, text="SplitForge",
                     font=ctk.CTkFont("Segoe UI", 16, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w")
        ctk.CTkLabel(name_f, text="Steam Showcase Studio",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C_DIM).pack(anchor="w")

        # Kaydırılabilir gövde: şablon + araçlar + çıktı klasörü hepsi burada.
        # Tek scroll alanı olduğu için şablon kartları artık kendi başına
        # büyüyüp boşluk açmıyor; sadece içeriği kadar yer kaplar, gövdenin
        # tamamı gerekirse kayar (pencere kısa olsa da hiçbir bölüm kesilmez).
        body = ctk.CTkScrollableFrame(
            sb, fg_color="transparent",
            scrollbar_button_color=C_BG4,
            scrollbar_button_hover_color=C_ACCENT)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        # Şablon başlığı
        self._section_label(body, "ŞABLON", row=0)

        # Şablon kartları — düz çerçeve, sadece kartlar kadar yer kaplar
        self._cards_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._cards_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        self._cards = []
        self._rebuild_template_cards()

        # Şablon yönetimi (oluşturma da bu tek sayfanın içinde)
        AnimButton(body, text="🧩  Şablonlar",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_DIM,
                   command=lambda: self._open_settings_page("Şablonlar")
                   ).grid(row=2, column=0, sticky="ew",
                          padx=10, pady=(0, 8))

        # Separator
        self._sep(body, row=3)

        # Araçlar
        self._section_label(body, "ARAÇLAR", row=4)

        tools_f = ctk.CTkFrame(body, fg_color="transparent")
        tools_f.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 6))

        AnimButton(tools_f, text="🎮  Steam Çizim Sayfası",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=self._open_steam_artwork
                   ).pack(fill="x", pady=2)

        AnimButton(tools_f, text="📋  Notlar / Console Kodları",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=lambda: self._open_settings_page("Notlar")
                   ).pack(fill="x", pady=2)

        AnimButton(tools_f, text="🎬  GIF / WebP Maker",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=self._open_gif_maker
                   ).pack(fill="x", pady=2)

        AnimButton(tools_f, text="🌐  Community Upload",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=self._run_steam_community_upload
                   ).pack(fill="x", pady=2)

        self._resume_upload_btn = AnimButton(tools_f, text="↻  Upload Devam",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=self._resume_steam_community_upload
                   )
        if self._has_resumable_upload():
            self._resume_upload_btn.pack(fill="x", pady=2)

        AnimButton(tools_f, text="⚙  Ayarlar",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=lambda: self._open_settings_page("Genel")
                   ).pack(fill="x", pady=2)

        # Separator
        self._sep(body, row=6)

        # Çıktı klasörü
        self._section_label(body, "ÇIKTI KLASÖRÜ", row=7)

        out_f = ctk.CTkFrame(body, fg_color=C_BG3, corner_radius=8)
        out_f.grid(row=8, column=0, sticky="ew", padx=8, pady=(0, 16))
        out_f.grid_columnconfigure(0, weight=1)

        self._out_lbl = ctk.CTkLabel(
            out_f, text=self._short_path(self.output_dir),
            font=ctk.CTkFont("Consolas", 9),
            text_color=C_DIM, anchor="w", wraplength=180)
        self._out_lbl.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

        AnimButton(out_f, text="Değiştir",
                   nc=C_BG3, hc=C_BG4,
                   height=26, corner_radius=6,
                   font=ctk.CTkFont("Segoe UI", 10),
                   text_color=C_DIM,
                   command=self._pick_output_dir
                   ).grid(row=1, column=0, sticky="ew",
                          padx=8, pady=(0, 8))

        # Seçili kartı işaretle
        self._sync_cards()

    # ── MAIN ──────────────────────────────────────────────
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        self._main = main
        main.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Üst: drop zone / önizleme
        self._drop = DropZone(main, self._on_file_drop, self._on_batch_drop,
                              initialdir_getter=lambda: self._cfg.get("last_input_dir", ""))
        self._drop.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        # Bölme grid'i ve metin katmanı önizlemenin üstünde fareyle sürüklenebilir;
        # çift tık = anında Böl, sağ tık = hizalama menüsü, tekerlek = zoom
        self._drop.bind_preview_mouse(self._grid_press, self._grid_drag, self._grid_release,
                                      on_double=self._preview_double_click,
                                      on_context=self._preview_context_menu,
                                      on_wheel=self._preview_zoom)
        self._grid_menu = Menu(self, tearoff=0, bg=C_BG2, fg=C_TEXT,
                               activebackground=C_ACCENT, activeforeground=C_BG0,
                               relief="flat", bd=0)
        for label, where in [("Ortala", "center"), ("Üste Hizala", "top"),
                             ("Alta Hizala", "bottom"), ("Sola Hizala", "left"),
                             ("Sağa Hizala", "right")]:
            self._grid_menu.add_command(label=label,
                                        command=lambda w=where: self._grid_snap(w))
        self._grid_menu.add_separator()
        self._grid_menu.add_command(label="🔍 Zoom Sıfırla", command=self._reset_zoom)
        self._grid_menu.add_command(label="🎮 Canlı Vitrin Aç/Kapat",
                                    command=self._toggle_live_showcase)
        self._grid_menu.add_command(label="✂ Böl", command=self._split_single)

        # Split önizleme (başta gizli)
        self._split_prev = SplitPreview(
            main,
            self._back_to_drop,
            self._open_output_dir,
            self._rerun_current,
            self._clear_outputs,
            self._open_file,
            self._copy_path,
            self._delete_output_file,
            on_upload=self._run_steam_community_upload,
        )
        # grid'e dahil et ama görünmez bırak
        self._split_prev.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self._split_prev.grid_remove()

        # Orta: aksiyon butonları
        btn_f = ctk.CTkFrame(main, fg_color="transparent")
        btn_f.grid(row=1, column=0, sticky="ew")
        btn_f.grid_columnconfigure((0, 1, 2, 3), weight=1)

        AnimButton(btn_f,
                   text="📂  Dosya Seç",
                   nc=C_BG3, hc=C_BG4,
                   height=42,
                   command=self._pick_file
                   ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        AnimButton(btn_f,
                   text="📁  Klasör Seç",
                   nc=C_BG3, hc=C_BG4,
                   height=42,
                   command=self._pick_folder
                   ).grid(row=0, column=1, sticky="ew", padx=5)

        AnimButton(btn_f,
                   text="✂  Böl",
                   nc=C_ACCENT, hc=C_ACC_LT,
                   variant="accent",
                   height=42,
                   text_color=C_BG0,
                   command=self._split_single
                   ).grid(row=0, column=2, sticky="ew", padx=5)

        AnimButton(btn_f,
                   text="⚡  Toplu Böl",
                   nc=C_ACC_DK, hc=C_ACCENT,
                   variant="accent",
                   height=42,
                   text_color=C_TEXT,
                   command=self._split_batch
                   ).grid(row=0, column=3, sticky="ew", padx=5)

        # Araç çubuğu: hızlı efekt paneli, canlı vitrin, bant sayısı.
        # (Eski "Konumu Seç, Gerisini Otomatik Böl" butonu kaldırıldı —
        # grid artık önizlemede doğrudan sürüklenip boyutlandırılıyor,
        # "Böl" gördüğün konumdan kesiyor, ayrı bir buton gereksizdi.)
        btn_f2 = ctk.CTkFrame(main, fg_color="transparent")
        btn_f2.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        btn_f2.grid_columnconfigure(2, weight=1)

        self._fx_btn = AnimButton(btn_f2, text="🎨  Efektler",
                   nc=C_BG3, hc=C_INDIGO, height=36,
                   font=ctk.CTkFont("Segoe UI", 12),
                   command=self._toggle_effects_panel)
        self._fx_btn.grid(row=0, column=0, padx=(0, 8))

        AnimButton(btn_f2, text="🎮  Canlı Vitrin", height=36,
                   nc=C_BG3, hc=C_INDIGO,
                   font=ctk.CTkFont("Segoe UI", 12),
                   command=self._toggle_live_showcase
                   ).grid(row=0, column=1)

        ctk.CTkLabel(btn_f2, text="Bant sayısı",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=C_DIM).grid(row=0, column=3, padx=(2, 6))

        self._band_entry = ctk.CTkEntry(btn_f2, fg_color=C_BG3, border_color=C_BORDER,
                                        text_color=C_TEXT, height=36, width=48,
                                        justify="center")
        self._band_entry.insert(0, str(self._cfg.get("multi_band_count", 3)))
        self._band_entry.grid(row=0, column=4)
        # Bant sayısı değişince ana önizlemedeki bant grid'i canlı yenilensin
        self._band_entry.bind("<KeyRelease>", lambda _e: (
            self._load_preview(self.current_path)
            if self.current_path and os.path.isfile(self.current_path) else None))

        # Status bar
        self._status = StatusBar(main)
        self._status.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self._status.set_right(self.template["name"])

    # ── Yardımcılar ───────────────────────────────────────
    def _sep(self, parent, row):
        ctk.CTkFrame(parent, height=1, fg_color=C_BORDER
                     ).grid(row=row, column=0, sticky="ew",
                             padx=14, pady=4)

    def _section_label(self, parent, text, row):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM
                     ).grid(row=row, column=0, sticky="w",
                             padx=18, pady=(6, 2))

    def _short_path(self, p):
        parts = p.replace("\\", "/").split("/")
        if len(parts) > 3:
            return "…/" + "/".join(parts[-2:])
        return p

    def _sync_cards(self):
        for card in self._cards:
            card.set_selected(card.tmpl is self.template or
                              card.tmpl["name"] == self.template["name"])

    def _rebuild_template_cards(self):
        for w in self._cards_frame.winfo_children():
            w.destroy()
        self._cards = []
        for t in TEMPLATES:
            card = TemplateCard(self._cards_frame, t, self._on_template_select)
            card.pack(fill="x", pady=3, padx=2)
            self._cards.append(card)
        self._sync_cards()

    # ── Olaylar ───────────────────────────────────────────
    def _on_template_select(self, tmpl):
        self.template = tmpl
        self._sync_cards()
        self._status.set(f"Şablon: {tmpl['name']}", C_ACCENT, C_ACCENT)
        self._status.set_right(tmpl["name"])
        if self.current_path and os.path.isfile(self.current_path):
            self._load_preview(self.current_path)

    def _remember_input_dir(self, d):
        if d and os.path.isdir(d):
            self._cfg["last_input_dir"] = d
            save_config(self._cfg)

    def _on_file_drop(self, path):
        self._batch_files = None
        self._grid_pos = None  # yeni dosyada grid varsayılan konuma (ortaya) döner
        self._grid_scale = 1.0
        # Sürüklenen/seçilen yol klasörse toplu giriş gibi davran
        if os.path.isdir(path):
            self.current_path = path
            self._drop.reset()
            self._remember_input_dir(path)
            self._status.set(f"Klasör: {os.path.basename(path)}", C_TEXT, C_SUCCESS)
            return
        self.current_path = path
        self._remember_input_dir(os.path.dirname(path))
        self._load_preview(path)
        self._status.set(f"Yüklendi: {os.path.basename(path)}", C_TEXT, C_SUCCESS)

    def _on_batch_drop(self, paths):
        exts = (".png", ".jpg", ".jpeg", ".webp", ".gif")
        valid = [p for p in paths if p.lower().endswith(exts)]
        if not valid:
            self._status.error("Seçilen dosyalar desteklenen bir formatta değil")
            return
        self._grid_pos = None
        self._batch_files = valid
        self.current_path = valid[0]
        self._remember_input_dir(os.path.dirname(valid[0]))
        self._load_preview(valid[0])
        self._status.set(f"{len(valid)} dosya seçildi (toplu bölme)", C_TEXT, C_SUCCESS)

    def _current_band_count(self) -> int:
        entry = getattr(self, "_band_entry", None)
        if entry is None:
            return 1
        try:
            return max(1, int(entry.get().strip()))
        except Exception:
            return 1

    def _load_preview(self, path):
        try:
            img = Image.open(path)
            if hasattr(img, "n_frames") and img.n_frames > 1:
                img.seek(0)
            img = autocrop_borders(img.convert("RGBA"), self._cfg)
            tmpl = self.template
            # Uniform + kaynak yeterince büyükse: interaktif önizleme (grid
            # fareyle sürüklenir, Böl o konumdan NATIVE keser). GIF'lerde de
            # geçerli. Kaynak şablondan BİRKAÇ px küçükse de grid çalışır —
            # setup ölçeği otomatik sığdırır (örn. 750 genişlik / 754 şablon
            # -> %99.5 seçim), kesimde bölge şablon boyutuna ölçeklenir;
            # görünmez bir fark, kullanıcı hiçbir şey ayarlamak zorunda kalmaz.
            if (tmpl.get("mode") == "uniform"
                    and img.width >= tmpl["width"] * 0.75
                    and img.height >= tmpl["height"] * 0.75):
                self._setup_interactive_preview(img)
                return
            self._pv = None
            self._grid_pos = None
            bands = self._current_band_count()
            preview = render_template_preview(img, tmpl, self._cfg, band_count=bands)
            summary = template_output_summary(img, tmpl, band_count=bands)
            # Kaynak şablondan küçükse büyütme kaçınılmaz — sessizce yapma, söyle
            if (tmpl.get("mode") == "uniform"
                    and (img.width < tmpl["width"] or img.height < tmpl["height"])):
                summary += (f" · ⚠ kaynak ({img.width}×{img.height}) şablondan küçük,"
                            f" büyütülerek kesilecek (kalite kaybı)")
            batch_count = len(self._batch_files) if self._batch_files else 0
            self._drop.show_image(preview, summary, batch_count=batch_count)
        except Exception as e:
            self._status.error(f"Önizleme hatası: {e}")

    # ── İnteraktif önizleme (sürüklenebilir/boyutlanabilir bölme grid'i) ──
    def _setup_interactive_preview(self, img):
        """Efektli tam görselden ölçekli bir taban cache'ler; grid overlay'i
        her sürüklemede sadece bu tabana yeniden çizilir (hızlı)."""
        tmpl = self.template
        tw_total, th = tmpl["width"], tmpl["height"]
        parts = tmpl["parts"]
        # Metin katmanı tabana BASILMAZ — overlay çiziminde canlı eklenir ki
        # kullanıcı metni fareyle sürükleyebilsin (taban cache'i bozulmadan).
        img = _apply_effects_pipeline(img, {**self._cfg, "text_overlay_enabled": False})
        W, H = img.size

        # Grid ölçeği kaynağa sığacak şekilde kısıtlanır (en az 1 bant)
        gscale = max(0.3, min(self._grid_scale, W / tw_total, H / th))
        bands_fit = max(1, min(self._current_band_count(), int(H // (th * gscale))))

        disp_w = max(self._drop.winfo_width(), 700) - 24
        disp_h = max(self._drop.winfo_height(), 480) - 24
        disp = img.convert("RGB")
        disp.thumbnail((max(1, disp_w), max(1, disp_h)), Image.LANCZOS)

        self._grid_scale = gscale
        prev = self._pv
        # Aynı dosyanın yeniden önizlemesinde (bant/efekt değişimi) zoom'u koru
        zoom = prev.get("zoom", 1.0) if prev and prev.get("img_size") == (W, H) else 1.0
        focus = prev.get("focus", (0.5, 0.5)) if prev and prev.get("img_size") == (W, H) else (0.5, 0.5)
        self._pv = {"img_size": (W, H), "disp": disp, "scale": disp.width / W,
                    "parts": parts, "band_h": th, "bands": bands_fit,
                    "slice_w": tw_total // parts, "tw_total": tw_total,
                    "zoom": zoom, "focus": focus}
        self._apply_grid_geometry()
        self._draw_grid_overlay()
        self._show_onboarding_tip()
        self._suggest_matching_template(W, H, gscale)

    def _view_crop(self):
        """Zoom/pan penceresi: gösterilen görselin disp uzayındaki kırpma
        dikdörtgeni (x0,y0,w,h). zoom=1'de tüm disp."""
        pv = self._pv
        dw, dh = pv["disp"].size
        z = pv.get("zoom", 1.0)
        cw, ch = dw / z, dh / z
        fx, fy = pv.get("focus", (0.5, 0.5))
        x0 = max(0.0, min(dw - cw, fx * dw - cw / 2))
        y0 = max(0.0, min(dh - ch, fy * dh - ch / 2))
        return x0, y0, cw, ch

    def _disp_from_event(self, e):
        """Gösterilen (zoom'lu) görsel koordinatı -> disp (zoom'suz) koordinat.
        Tüm hit-test/sürükleme bunun üstünden çalışır, böylece zoom'da da
        grid/metin doğru yerden yakalanır."""
        pv = self._pv
        z = pv.get("zoom", 1.0)
        if z <= 1.0:
            return e.x, e.y
        x0, y0, _cw, _ch = self._view_crop()
        return x0 + e.x / z, y0 + e.y / z

    def _preview_zoom(self, e):
        pv = self._pv
        if not pv:
            return
        z0 = pv.get("zoom", 1.0)
        z = z0 * (1.15 if e.delta > 0 else 1 / 1.15)
        z = max(1.0, min(5.0, z))
        if abs(z - z0) < 0.001:
            return
        # Fare altındaki noktayı sabit tut (odak oraya kaysın)
        dw, dh = pv["disp"].size
        dx, dy = self._disp_from_event(e)
        pv["focus"] = (dx / dw, dy / dh)
        pv["zoom"] = z
        if z <= 1.0:
            pv["focus"] = (0.5, 0.5)
        self._draw_grid_overlay()

    def _suggest_matching_template(self, W, H, gscale):
        """Seçili şablon kaynağa sığmayıp büyütme gerekiyorsa, kaynağa %100
        oturan başka bir uniform şablon varsa kullanıcıya söyle — sessiz
        büyütme sürprizi yerine yol göster."""
        if gscale >= 0.95:
            return
        best = None
        for t2 in TEMPLATES:
            if t2 is self.template or t2.get("mode") != "uniform":
                continue
            if W >= t2["width"] and H >= t2["height"]:
                coverage = (t2["width"] * t2["height"]) / (W * H)
                if best is None or coverage > best[1]:
                    best = (t2, coverage)
        if best:
            name = best[0]["name"]
            # _on_file_drop'un "Yüklendi" mesajı bunu ezmesin diye ertele
            self.after(250, lambda: self._status.set(
                f"💡 Bu kaynağa ({W}×{H}) birebir uyan şablon: {name} — sol menüden seç",
                C_ACC_LT, C_ACC_LT, auto_reset=False))

    def _show_onboarding_tip(self):
        """İlk interaktif önizlemede TEK seferlik rehber balonu — grid'in
        sürüklenebildiğini bilmeyen kullanıcı için. 9 sn sonra kaybolur,
        bir daha gösterilmez (onboarding_tips_shown)."""
        if self._cfg.get("onboarding_tips_shown"):
            return
        self._cfg["onboarding_tips_shown"] = True
        save_config(self._cfg)
        tip = ctk.CTkLabel(
            self._drop,
            text="  💡 Grid'i fareyle sürükle · köşesinden boyutlandır · sağ tık: hizalama menüsü  ",
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            text_color=C_BG0, fg_color=C_ACCENT, corner_radius=10,
            padx=10, pady=6)
        tip.place(relx=0.5, y=16, anchor="n")
        self.after(9000, lambda: tip.winfo_exists() and tip.destroy())

    def _apply_grid_geometry(self):
        """Ölçekten grid boyutunu türetir, konumu kaynağa göre kıskaçlar."""
        pv = self._pv
        W, H = pv["img_size"]
        gscale = self._grid_scale
        gw = int(round(pv["tw_total"] * gscale))
        gh = int(round(pv["band_h"] * pv["bands"] * gscale))
        pv["grid"] = (gw, gh)
        if self._grid_pos is None:
            gx, gy = (W - gw) // 2, max(0, (H - gh) // 2)  # varsayılan: ortala
        else:
            gx, gy = self._grid_pos
        self._grid_pos = (max(0, min(W - gw, int(gx))), max(0, min(H - gh, int(gy))))

    def _draw_grid_overlay(self):
        pv = self._pv
        if not pv:
            return
        base = pv["disp"].copy()
        # Metin katmanı canlı: yüzde tabanlı konum küçük kopyada da orantılı
        # aynı yere düşer; kutusu hit-test için saklanır (fareyle sürüklenir).
        if self._cfg.get("text_overlay_enabled"):
            base = apply_text_overlay(base, self._cfg).convert("RGB")
            pv["text_bbox"] = text_overlay_bbox(base.size, self._cfg)
        else:
            pv["text_bbox"] = None
        d = ImageDraw.Draw(base, "RGBA")
        s = pv["scale"]
        gscale = self._grid_scale
        gx, gy = self._grid_pos
        gw, gh = pv["grid"]
        parts, th = pv["parts"], pv["band_h"]
        th_g = th * gscale
        # Gerçek kesim sınırları (kalan px ilk parçalarda: 754 -> 151,151,151,151,150)
        bounds = uniform_slice_bounds(pv["tw_total"], parts)
        for b in range(pv["bands"]):
            y1 = gy + b * th_g
            for i, (bx1, bx2) in enumerate(bounds):
                x1 = gx + bx1 * gscale
                x2 = gx + bx2 * gscale
                fill = (249, 115, 22, 26) if (b * parts + i) % 2 == 0 else (99, 102, 241, 22)
                d.rectangle((x1 * s, y1 * s, x2 * s, (y1 + th_g) * s),
                            fill=fill, outline=(249, 115, 22, 255), width=2)
        # Sağ-alt köşe boyutlandırma tutamacı
        cx, cy = (gx + gw) * s, (gy + gh) * s
        d.rectangle((cx - 7, cy - 7, cx + 7, cy + 7),
                    fill=(249, 115, 22, 255), outline=(8, 8, 8, 255), width=2)

        # Canlı vitrin PiP'i: parçaların Steam boşluklarıyla dizilmiş hali,
        # sağ-alt köşede, sürüklerken canlı güncellenir
        if self._live_showcase:
            pip = self._compose_pip_showcase(base)
            px = base.width - pip.width - 10
            py = base.height - pip.height - 10
            base.paste(pip, (px, py))
            d.rectangle((px - 1, py - 1, px + pip.width, py + pip.height),
                        outline=(249, 115, 22, 255), width=1)

        W, H = pv["img_size"]
        patch = " · patch açık" if self.template.get("patch") else ""
        th_total = th * pv["bands"]
        # Ölçek durumunu AÇIKÇA söyle: %83 gibi bir oran yerine ne olacağını yaz
        if abs(gscale - 1.0) < 0.01:
            scale_txt = ""
        elif gscale < 1.0:
            scale_txt = (f" · ⚠ seçim {gw}×{gh} → {pv['tw_total']}×{th_total}'e "
                         f"BÜYÜTÜLECEK (kalite kaybı)")
        else:
            scale_txt = f" · seçim {gw}×{gh} → {pv['tw_total']}×{th_total}'e küçültülecek"
        req = self._current_band_count()
        bant_txt = f"{pv['bands']} bant"
        if req > pv["bands"]:
            bant_txt += f" — {req} istendi, kaynağın boyu yetmiyor"
        first_w = bounds[0][1] - bounds[0][0]
        info = (f"{pv['bands'] * parts} parça ({bant_txt}) · konum {gx},{gy}"
                f"{scale_txt} · parça {first_w}×{th}px · kaynak {W}×{H}px{patch}"
                f" · 🖱 sürükle / köşeden boyutlandır")
        # Zoom penceresi: gösterilen görüntüyü fare odağı etrafından kırp+büyüt
        z = pv.get("zoom", 1.0)
        if z > 1.0:
            x0, y0, cw, ch = self._view_crop()
            crop = base.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))
            base = crop.resize(pv["disp"].size, Image.LANCZOS)
            info += f" · 🔍 %{round(z * 100)} (tekerlek: zoom, sağ tık: sıfırla)"
        batch_count = len(self._batch_files) if self._batch_files else 0
        self._drop.show_image(base, info, batch_count=batch_count)

    def _grid_press(self, e):
        pv = self._pv
        if not pv:
            return
        s = pv["scale"]
        dx, dy = self._disp_from_event(e)   # zoom/pan -> disp koordinatı
        gx, gy = self._grid_pos
        gw, gh = pv["grid"]
        # Öncelik 1: metin katmanının üstüne basıldıysa metni sürükle
        tb = pv.get("text_bbox")
        if tb and tb[0] - 4 <= dx <= tb[2] + 4 and tb[1] - 4 <= dy <= tb[3] + 4:
            disp = pv["disp"]
            tw_txt, th_txt = tb[2] - tb[0], tb[3] - tb[1]
            denom_x = max(1, disp.width - tw_txt)
            denom_y = max(1, disp.height - th_txt)
            pv["press"] = ("text", dx, dy, tb[0] / denom_x, tb[1] / denom_y,
                           denom_x, denom_y)
            return
        cx, cy = (gx + gw) * s, (gy + gh) * s
        if abs(dx - cx) <= 12 and abs(dy - cy) <= 12:
            # köşe tutamacı: boyutlandırma (delta tabanlı, DPI'dan bağımsız)
            pv["press"] = ("resize", dx, dy, self._grid_scale, max(1.0, gw * s))
        else:
            pv["press"] = ("move", dx, dy, gx, gy)

    def _preview_double_click(self, _e=None):
        """Önizlemeye çift tık: gridin olduğu yerden anında böl."""
        if self._pv:
            self._split_single()

    def _preview_context_menu(self, e):
        if self._pv:
            try:
                self._grid_menu.tk_popup(e.x_root, e.y_root)
            finally:
                self._grid_menu.grab_release()

    def _grid_snap(self, where: str):
        pv = self._pv
        if not pv:
            return
        W, H = pv["img_size"]
        gw, gh = pv["grid"]
        gx, gy = self._grid_pos
        if where == "center":
            gx, gy = (W - gw) // 2, (H - gh) // 2
        elif where == "top":
            gy = 0
        elif where == "bottom":
            gy = H - gh
        elif where == "left":
            gx = 0
        elif where == "right":
            gx = W - gw
        self._grid_pos = (max(0, gx), max(0, gy))
        self._draw_grid_overlay()

    def _reset_zoom(self):
        if self._pv:
            self._pv["zoom"] = 1.0
            self._pv["focus"] = (0.5, 0.5)
            self._draw_grid_overlay()

    def _toggle_live_showcase(self):
        self._live_showcase = not self._live_showcase
        if self._pv:
            self._draw_grid_overlay()

    # ── Hızlı efekt paneli (önizleme üstünde, ayarlar sayfası DEĞİL) ──
    def _toggle_effects_panel(self):
        if getattr(self, "_fx_open", False):
            if getattr(self, "_fx_panel", None) is not None:
                self._fx_panel.place_forget()
            self._fx_open = False
            return
        self._build_effects_panel()
        # Önizlemenin solundaki koyu boşluğa otur (görsel ortalı; canlı
        # geri bildirim için önizleme görünür kalır). Genişlik constructor'da.
        self._fx_panel.place(x=10, y=10, relheight=0.96)
        self._fx_panel.lift()
        self._fx_open = True

    def _build_effects_panel(self):
        """Efekt panelini o anki cfg'den taze kurar. Her değişiklik cfg'ye
        yazılır, kaydedilir ve önizleme canlı yenilenir (ayarlar sayfasındaki
        'Kaydet' beklemeye gerek yok — WYSIWYG)."""
        if getattr(self, "_fx_panel", None) is not None:
            self._fx_panel.destroy()
        cfg = self._cfg
        panel = ctk.CTkScrollableFrame(
            self._drop, fg_color=C_BG2, corner_radius=12, width=300,
            scrollbar_button_color=C_BG4, scrollbar_button_hover_color=C_ACCENT)
        self._fx_panel = panel

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(head, text="🎨  Efektler",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(side="left", padx=4)
        AnimButton(head, text="✕", width=30, height=26, nc=C_BG3, hc=C_BG4,
                   text_color=C_DIM, command=lambda: panel.place_forget()
                   ).pack(side="right", padx=2)

        def live(_=None):
            save_config(cfg)
            if self.current_path and os.path.isfile(self.current_path):
                self._load_preview(self.current_path)

        def section(title):
            ctk.CTkLabel(panel, text=title, font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                         text_color=C_DIM).pack(anchor="w", padx=6, pady=(10, 2))

        def enable_check(label, key):
            var = BooleanVar(value=bool(cfg.get(key, False)))
            def toggle():
                cfg[key] = bool(var.get())
                live()
            ctk.CTkCheckBox(panel, text=label, variable=var,
                            font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT,
                            fg_color=C_ACCENT, hover_color=C_ACC_LT, checkmark_color=C_BG0,
                            command=toggle).pack(anchor="w", padx=6, pady=3)
            return var

        def slider_row(label, key, default, frm=0, to=100):
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=(0, 2))
            top = ctk.CTkFrame(row, fg_color="transparent"); top.pack(fill="x")
            ctk.CTkLabel(top, text=label, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(side="left")
            val = ctk.CTkLabel(top, text="", font=ctk.CTkFont("Consolas", 10, weight="bold"),
                               text_color=C_ACCENT)
            val.pack(side="right")
            s = ctk.CTkSlider(row, from_=frm, to=to, button_color=C_ACCENT,
                              button_hover_color=C_ACC_LT, progress_color=C_ACCENT, fg_color=C_BG4)
            s.pack(fill="x")
            raw = cfg.get(key, default)
            s.set(int(raw) if raw is not None else default)
            def on(v):
                cfg[key] = int(float(v)); val.configure(text=str(int(float(v)))); live()
            s.configure(command=on); val.configure(text=str(int(s.get())))
            return s

        def color_entry(label, key, default):
            ctk.CTkLabel(panel, text=label, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=6)
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=(0, 4))
            e = ctk.CTkEntry(row, fg_color=C_BG3, border_color=C_BORDER, text_color=C_TEXT, height=30)
            e.insert(0, cfg.get(key, default))
            e.pack(side="left", fill="x", expand=True)
            def commit(_=None):
                cfg[key] = e.get().strip() or default; live()
            e.bind("<FocusOut>", commit); e.bind("<Return>", commit)
            def pick():
                c = colorchooser.askcolor(color=cfg.get(key, default))[1]
                if c:
                    e.delete(0, "end"); e.insert(0, c); cfg[key] = c; live()
            AnimButton(row, text="🎨", width=34, height=30, nc=C_BG3, hc=C_BG4,
                       command=pick).pack(side="left", padx=(4, 0))

        # ── ÖN İŞLEME ──
        section("ÖN İŞLEME")
        enable_check("Kenar boşluğunu otomatik kırp (autocrop)", "autocrop_enabled")

        # ── OTOMATİK İYİLEŞTİR ──
        section("OTOMATİK İYİLEŞTİR")
        enable_check("Kontrast/doygunluk/keskinlik dengele", "auto_enhance_enabled")
        slider_row("Yoğunluk", "auto_enhance_intensity", 50)

        # ── BORDER FX ──
        section("BORDER FX (KENARLIK)")
        templates = list_border_templates()
        if templates:
            enable_check("Kenarlık uygula", "border_fx_enabled")
            tvar = StringVar(value=cfg.get("border_fx_template", templates[0]) or templates[0])
            def on_tmpl(v):
                cfg["border_fx_template"] = v; live()
            ctk.CTkOptionMenu(panel, values=templates, variable=tvar, command=on_tmpl,
                              fg_color=C_BG3, button_color=C_ACCENT, button_hover_color=C_ACC_LT,
                              dropdown_fg_color=C_BG3, dropdown_hover_color=C_BG4,
                              text_color=C_TEXT).pack(fill="x", padx=6, pady=(0, 4))
            color_entry("Renk (#RRGGBB)", "border_fx_color", "#8B5CF6")
            slider_row("Opaklık", "border_fx_opacity", 100)
            slider_row("Glow", "border_fx_glow", 35)
        else:
            ctk.CTkLabel(panel, text="Border Templates klasöründe PNG yok.",
                         font=ctk.CTkFont("Segoe UI", 10), text_color=C_ERROR).pack(anchor="w", padx=6, pady=4)

        # ── METİN KATMANI ──
        section("METİN KATMANI")
        enable_check("Metin ekle", "text_overlay_enabled")
        ctk.CTkLabel(panel, text="Metin (önizlemede sürüklenebilir)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_DIM).pack(anchor="w", padx=6)
        te = ctk.CTkEntry(panel, fg_color=C_BG3, border_color=C_BORDER, text_color=C_TEXT,
                          height=30, placeholder_text="Başlık / imza")
        te.insert(0, cfg.get("text_overlay_text", ""))
        te.pack(fill="x", padx=6, pady=(0, 4))
        def commit_text(_=None):
            cfg["text_overlay_text"] = te.get().strip(); live()
        te.bind("<FocusOut>", commit_text); te.bind("<Return>", commit_text)
        color_entry("Renk (#RRGGBB)", "text_overlay_color", "#FFFFFF")
        slider_row("Boyut", "text_overlay_size", 6, frm=1, to=30)
        slider_row("Opaklık", "text_overlay_opacity", 100)

    def _compose_pip_showcase(self, base):
        """Grid'in mevcut konumundaki parçaları Steam boşluklarıyla dizen
        küçük picture-in-picture kompoziti (ölçekli tabandan kesildiği için
        her sürükleme karesinde ucuz)."""
        pv = self._pv
        s = pv["scale"]
        gscale = self._grid_scale
        gx, gy = self._grid_pos
        parts, th = pv["parts"], pv["band_h"]
        sw_g = pv["slice_w"] * gscale
        th_g = th * gscale
        gap, pad = 3, 8
        cell_w = 26
        cell_h = max(1, int(cell_w * th / max(1, pv["slice_w"])))
        rows = pv["bands"]
        pip = Image.new("RGB", (pad * 2 + parts * cell_w + (parts - 1) * gap,
                                pad * 2 + rows * cell_h + (rows - 1) * gap), (23, 26, 33))
        for b in range(rows):
            for i in range(parts):
                box = (int((gx + i * sw_g) * s), int((gy + b * th_g) * s),
                       max(int((gx + i * sw_g) * s) + 1, int((gx + (i + 1) * sw_g) * s)),
                       max(int((gy + b * th_g) * s) + 1, int((gy + (b + 1) * th_g) * s)))
                cell = base.crop(box).resize((cell_w, cell_h), Image.BILINEAR)
                pip.paste(cell, (pad + i * (cell_w + gap), pad + b * (cell_h + gap)))
        # Önizlemeye sığdır (en fazla ~%55 yükseklik)
        pip.thumbnail((max(60, base.width // 3), max(60, int(base.height * 0.55))),
                      Image.BILINEAR)
        return pip

    def _grid_release(self, _e=None):
        pv = self._pv
        if not pv:
            return
        press = pv.pop("press", None)
        if press and press[0] == "text":
            save_config(self._cfg)  # sürüklenen metin konumu kalıcı olsun

    def _grid_drag(self, e):
        pv = self._pv
        if not pv or "press" not in pv:
            return
        mode = pv["press"][0]
        W, H = pv["img_size"]
        ex, ey = self._disp_from_event(e)   # zoom/pan -> disp koordinatı
        if mode == "text":
            _, px, py, x0_pct, y0_pct, denom_x, denom_y = pv["press"]
            xp = max(0.0, min(1.0, x0_pct + (ex - px) / denom_x))
            yp = max(0.0, min(1.0, y0_pct + (ey - py) / denom_y))
            self._cfg["text_overlay_custom_pos"] = [round(xp, 4), round(yp, 4)]
            self._draw_grid_overlay()
            return
        if mode == "resize":
            _, px, py, scale0, gw_disp0 = pv["press"]
            new_scale = scale0 * (1 + (ex - px) / gw_disp0)
            # kaynağa sığsın: konum sabit, köşe içeride kalmalı
            gx, gy = self._grid_pos
            max_scale = min((W - gx) / pv["tw_total"],
                            (H - gy) / (pv["band_h"] * pv["bands"]))
            new_scale = max(0.3, min(new_scale, max_scale))
            if abs(new_scale - self._grid_scale) < 0.003:
                return
            self._grid_scale = new_scale
            self._apply_grid_geometry()
            self._draw_grid_overlay()
            return
        _, px, py, ox, oy = pv["press"]
        s = pv["scale"] or 1.0
        gw, gh = pv["grid"]
        gx = int(max(0, min(W - gw, ox + (ex - px) / s)))
        gy = int(max(0, min(H - gh, oy + (ey - py) / s)))
        if (gx, gy) != self._grid_pos:
            self._grid_pos = (gx, gy)
            self._draw_grid_overlay()

    def _pick_file(self):
        initial = self._cfg.get("last_input_dir", "")
        kwargs = {"filetypes": [("Resimler", "*.png;*.jpg;*.jpeg;*.webp;*.gif")]}
        if initial and os.path.isdir(initial):
            kwargs["initialdir"] = initial
        paths = filedialog.askopenfilenames(**kwargs)
        if not paths:
            return
        if len(paths) == 1:
            self._on_file_drop(paths[0])
        else:
            self._on_batch_drop(list(paths))

    def _pick_folder(self):
        initial = self._cfg.get("last_input_dir", "")
        kwargs = {}
        if initial and os.path.isdir(initial):
            kwargs["initialdir"] = initial
        p = filedialog.askdirectory(**kwargs)
        if p:
            self._batch_files = None
            self.current_path = p
            self._drop.reset()
            self._remember_input_dir(p)
            self._status.set(f"Klasör: {os.path.basename(p)}", C_TEXT, C_SUCCESS)

    def _pick_output_dir(self):
        p = filedialog.askdirectory()
        if p:
            self.output_dir = p
            self._out_lbl.configure(text=self._short_path(p))
            self._cfg["output_dir"] = p
            save_config(self._cfg)
            self._status.set("Çıktı klasörü güncellendi", C_SUCCESS, C_SUCCESS)

    # ── Bölme işlemleri ───────────────────────────────────
    def _split_single(self):
        if self._splitting:
            self._status.error("Bir bölme işlemi zaten sürüyor")
            return
        if self._batch_files:
            self._split_batch()
            return
        if not self.current_path or os.path.isdir(self.current_path):
            self._status.error("Önce tek bir resim seç")
            return
        # Büyük GIF + gifsicle UI'yi dondurmasın diye arka planda işle
        path = self.current_path
        template = self.template
        cfg = self._cfg
        outdir = self.output_dir
        # İnteraktif grid aktifse Böl, önizlemede GÖRÜNEN konumdan native
        # keser (WYSIWYG) — preset_origin'li manuel crop yolu saf PIL olduğu
        # için worker thread'de güvenle çalışır.
        grid_origin = self._grid_pos if self._pv else None
        grid_bands = self._pv["bands"] if self._pv else 1
        grid_scale = self._grid_scale if self._pv else 1.0
        self._splitting = True
        self._status.busy("Bölünüyor...")

        def worker():
            try:
                if grid_origin is not None and path.lower().endswith(".gif"):
                    # GIF + interaktif grid: tüm kareler grid konumundan
                    # native kesilir (cover-crop büyütmesi yok)
                    created = split_gif_frames(
                        path, outdir, template, cfg,
                        preset_origin=grid_origin, region_scale=grid_scale,
                        band_count=grid_bands)
                elif grid_origin is not None:
                    created = manual_crop_with_template(
                        self, path, outdir, template, cfg,
                        band_count=grid_bands, preset_origin=grid_origin,
                        region_scale=grid_scale)
                else:
                    created = process_image(path, outdir, template, cfg)
                self.after(0, lambda: self._on_split_done(created))
            except Exception as e:
                self.after(0, lambda e=e: self._status.error(str(e)))
            finally:
                self.after(0, lambda: setattr(self, "_splitting", False))

        threading.Thread(target=worker, daemon=True).start()

    def _on_split_done(self, created):
        self._status.ok(f"{len(created)} parça oluşturuldu ✓")
        self._show_split_preview(created)

    def _show_split_preview(self, file_paths: list):
        """DropZone'u gizle, SplitPreview'ı göster ve yükle."""
        self._last_outputs = list(file_paths)
        self._drop.grid_remove()
        self._split_prev.grid()
        # Vitrin simülasyonunda satır başına parça sayısı: uniform şablonda
        # şablonun kendi parça sayısı (her bant bir satır), diğerlerinde 5'e kadar.
        parts = self.template.get("parts")
        per_row = parts if isinstance(parts, int) and parts > 0 else min(5, max(1, len(file_paths)))
        self._split_prev.load(file_paths, parts_per_row=per_row)
        if self._cfg.get("open_output_after_process"):
            open_folder(self.output_dir)
        if self._cfg.get("auto_upload"):
            self._run_steam_community_upload(file_paths)

    def _back_to_drop(self):
        """SplitPreview'dan DropZone'a geri dön."""
        self._split_prev.grid_remove()
        self._drop.grid()
        self._status.set("Hazır", C_DIM, C_SUCCESS, auto_reset=False)

    def _split_batch(self):
        if self._splitting:
            self._status.error("Bir bölme işlemi zaten sürüyor")
            return

        if self._batch_files:
            file_paths = list(self._batch_files)
        elif self.current_path and os.path.isdir(self.current_path):
            exts = (".png", ".jpg", ".jpeg", ".webp", ".gif")
            file_paths = [os.path.join(self.current_path, f)
                          for f in os.listdir(self.current_path)
                          if f.lower().endswith(exts)]
        else:
            self._status.error("Önce bir klasör veya birden fazla dosya seç")
            return

        if not file_paths:
            self._status.error("İşlenecek resim bulunamadı")
            return

        total = len(file_paths)
        # İşlem boyunca şablon/ayar değişse bile tutarlı kalsın diye sabitle
        template = self.template
        cfg = self._cfg
        outdir = self.output_dir
        self._splitting = True
        # Progress dialog
        dlg = ctk.CTkToplevel(self)
        dlg.title("İşleniyor")
        dlg.geometry("400x170")
        dlg.configure(fg_color=C_BG2)
        dlg.grab_set()
        dlg.resizable(False, False)

        ctk.CTkLabel(dlg, text="Toplu bölme işlemi",
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color=C_TEXT).pack(pady=(16, 4))

        lbl = ctk.CTkLabel(dlg, text="Hazırlanıyor...",
                           font=ctk.CTkFont("Segoe UI", 10),
                           text_color=C_DIM)
        lbl.pack()

        bar = ctk.CTkProgressBar(dlg, width=360,
                                 progress_color=C_ACCENT,
                                 fg_color=C_BG4)
        bar.pack(pady=8)
        bar.set(0)

        created_all = []; errors = []; renamed = []
        # Worker ile UI arasında paylaşılan iptal bayrağı. Pencerenin X'i de
        # İptal gibi davranır — eskiden X'e basınca worker dlg.after üzerinde
        # çöküyor ve _splitting sonsuza kadar True kalıyordu (bir daha hiçbir
        # bölme çalışmıyordu).
        cancel_flag = threading.Event()

        def request_cancel():
            cancel_flag.set()
            lbl.configure(text="İptal ediliyor... (mevcut dosya bitince durur)")

        AnimButton(dlg, text="İptal Et", height=30, text_color=C_ERROR,
                   font=ctk.CTkFont("Segoe UI", 11),
                   command=request_cancel).pack(fill="x", padx=20, pady=(2, 12))
        dlg.protocol("WM_DELETE_WINDOW", request_cancel)

        def worker():
            # Aynı isim gövdesine (stem) sahip FARKLI kaynak dosyalar aynı
            # çıktı adını üretip birbirinin üstüne yazmasın diye say.
            seen_stems = {}
            for i, path in enumerate(file_paths, 1):
                if cancel_flag.is_set():
                    break
                fname = os.path.basename(path)
                try:
                    stem = os.path.splitext(fname)[0]
                    key = stem.lower()
                    count = seen_stems.get(key, 0)
                    seen_stems[key] = count + 1
                    override = stem if count == 0 else f"{stem}_{count + 1}"
                    if override != stem:
                        renamed.append(f"{fname} -> {override}")
                    r = process_image(path, outdir, template, cfg, name_override=override)
                    created_all.extend(r)
                except Exception as e:
                    errors.append(f"{fname}: {e}")
                # self.after: dialog yok edilmiş olsa bile App ayakta olduğu
                # için güvenli; _upd kendi içinde dlg'nin varlığını kontrol eder.
                self.after(0, lambda i=i, n=fname: _upd(i, n))
            self.after(0, _done)

        def _upd(i, name):
            if not dlg.winfo_exists():
                return
            bar.set(i / total)
            lbl.configure(text=f"{name}  ({i}/{total})")

        def _done():
            self._splitting = False
            if dlg.winfo_exists():
                dlg.destroy()
            cancelled = cancel_flag.is_set()
            if cancelled:
                self._status.error(
                    f"İptal edildi — {len(created_all)} parça oluşturulmuştu")
            elif errors:
                self._status.error(
                    f"{len(created_all)} parça, {len(errors)} hata")
            else:
                self._status.ok(
                    f"{len(created_all)} parça oluşturuldu ({total} dosya) ✓")
            if created_all:
                self._show_split_preview(created_all)
            # Raporu hata VEYA çakışma-yeniden-adlandırma varsa göster
            if not cancelled and (errors or renamed):
                self._show_batch_report(total, created_all, errors, renamed)

        threading.Thread(target=worker, daemon=True).start()

    def _open_output_dir(self):
        open_folder(self.output_dir)

    def _open_file(self, path: str):
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            else:
                webbrowser.open(path)
        except Exception as e:
            self._status.error(f"Açılamadı: {e}")

    def _copy_path(self, path: str):
        self.clipboard_clear()
        self.clipboard_append(path)
        self._status.set("Dosya yolu panoya kopyalandı", C_SUCCESS, C_SUCCESS)

    def _last_upload_paths(self):
        manifest = os.path.join(self.output_dir, "steam_upload_manifest.json")
        status_path = upload_status_path(manifest)
        return manifest, status_path

    def _has_resumable_upload(self) -> bool:
        manifest, status_path = self._last_upload_paths()
        if not os.path.exists(manifest) or not os.path.exists(status_path):
            return False
        try:
            with open(manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(status_path, "r", encoding="utf-8") as f:
                status = json.load(f)
            if status.get("state") == "done":
                return False
            files = [item["path"] for item in data.get("files", []) if os.path.exists(item.get("path", ""))]
            completed = set(status.get("completed", []))
            remaining = [p for p in files if p not in completed]
            return bool(remaining)
        except Exception:
            return False

    def _refresh_resume_upload_button(self):
        btn = getattr(self, "_resume_upload_btn", None)
        if not btn:
            return
        if self._has_resumable_upload():
            if not btn.winfo_ismapped():
                btn.pack(fill="x", pady=2)
        else:
            if btn.winfo_ismapped():
                btn.pack_forget()

    def _delete_output_file(self, path: str):
        try:
            if os.path.isfile(path):
                os.remove(path)
            self._last_outputs = [p for p in self._last_outputs if p != path]
            self._split_prev.load(self._last_outputs)
            self._status.ok("Dosya silindi")
        except Exception as e:
            self._status.error(f"Silinemedi: {e}")

    def _rerun_current(self):
        if self._batch_files:
            self._split_batch()
            return
        if not self.current_path:
            self._status.error("Yeniden işlemek için önce dosya veya klasör seç")
            return
        if os.path.isdir(self.current_path):
            self._split_batch()
        else:
            self._split_single()

    def _clear_outputs(self, file_paths: list):
        if not file_paths:
            self._status.error("Temizlenecek son çıktı yok")
            return
        if not messagebox.askyesno(
                "Çıktıları Temizle",
                f"{len(file_paths)} çıktı dosyası silinecek. Devam edilsin mi?"):
            return
        removed = 0
        errors = 0
        for path in file_paths:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    removed += 1
            except Exception:
                errors += 1
        self._last_outputs = []
        self._split_prev.load([])
        if errors:
            self._status.error(f"{removed} dosya silindi, {errors} hata")
        else:
            self._status.ok(f"{removed} çıktı temizlendi")

    def _show_batch_report(self, total: int, created: list, errors: list, renamed: list | None = None):
        renamed = renamed or []
        win = ctk.CTkToplevel(self)
        win.title("Toplu İşlem Raporu")
        win.geometry("520x360")
        win.configure(fg_color=C_BG1)
        win.grab_set()

        ctk.CTkLabel(win, text="Toplu İşlem Raporu",
                     font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=16, pady=(16, 4))

        total_size = 0
        for path in created:
            try:
                total_size += os.path.getsize(path)
            except Exception:
                pass
        size_mb = total_size / (1024 * 1024)
        summary = (
            f"İşlenen dosya: {total}\n"
            f"Oluşan çıktı: {len(created)}\n"
            f"Toplam boyut: {size_mb:.2f} MB\n"
            f"Hata: {len(errors)}\n"
            f"Çakışma önlendi: {len(renamed)}\n"
            f"Çıktı klasörü: {self.output_dir}"
        )
        ctk.CTkLabel(win, text=summary,
                     font=ctk.CTkFont("Consolas", 11),
                     text_color=C_DIM,
                     justify="left").pack(anchor="w", padx=16, pady=8)

        if renamed:
            ctk.CTkLabel(win, text="AYNI İSİMLİ FARKLI DOSYALAR YENİDEN ADLANDIRILDI",
                         font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                         text_color=C_ACCENT).pack(anchor="w", padx=16, pady=(4, 2))
            rbox = Text(win, bg=C_BG2, fg=C_TEXT, insertbackground=C_ACCENT,
                       font=("Consolas", 9), wrap="word", relief="flat",
                       padx=10, pady=8, height=min(5, len(renamed) + 1))
            rbox.pack(fill="x", padx=16, pady=(0, 8))
            rbox.insert("1.0", "\n".join(renamed))
            rbox.configure(state="disabled")

        if errors:
            box = Text(win, bg=C_BG2, fg=C_ERROR, insertbackground=C_ACCENT,
                       font=("Consolas", 9), wrap="word", relief="flat",
                       padx=10, pady=10, height=8)
            box.pack(fill="both", expand=True, padx=16, pady=(4, 10))
            box.insert("1.0", "\n".join(errors))
            box.configure(state="disabled")

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=(0, 12))
        AnimButton(btns, text="Klasörde Aç", variant="accent",
                   height=34, text_color=C_BG0,
                   command=self._open_output_dir).pack(side="left", fill="x", expand=True, padx=(0, 6))
        AnimButton(btns, text="Kapat", height=34,
                   command=win.destroy).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _prepare_steam_community_manifest(self, file_paths: list[str]) -> str:
        return build_steam_upload_manifest(file_paths, self._cfg, self.output_dir, self.template)

    def _upload_in_progress(self) -> bool:
        proc = getattr(self, "_upload_proc", None)
        return proc is not None and proc.poll() is None

    def _run_steam_community_upload(self, file_paths: list[str] | None = None):
        # Aynı anda iki uploader süreci aynı tarayıcı profilini (.steam_browser_profile)
        # kilitleyip çakışır — aktif süreç bitmeden yenisi başlatılmaz.
        if self._upload_in_progress():
            self._status.error("Zaten süren bir upload var — önce onu bitir veya iptal et")
            return
        if getattr(self, "_queue_running", False):
            self._status.error("Toplu upload kuyruğu çalışıyor — manuel upload beklemede")
            return
        files = list(file_paths or self._last_outputs)
        if not files:
            self._status.error("Steam upload için önce çıktı oluştur")
            return
        try:
            manifest = self._prepare_steam_community_manifest(files)
            status_path = upload_status_path(manifest)
            if file_paths is None and os.path.exists(status_path):
                os.remove(status_path)
        except Exception as e:
            self._status.error(f"Manifest hazırlanamadı: {e}")
            return
        uploader = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_community_uploader.py")
        try:
            self._upload_proc = subprocess.Popen(
                [sys.executable, uploader, "--manifest", manifest],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                creationflags=0,
            )
            self._status.set("Steam Community uploader açıldı", C_SUCCESS, C_SUCCESS)
            self._open_upload_monitor(status_path, files)
            self._refresh_resume_upload_button()
            self._watch_upload_history(status_path, len(files), f"{len(files)} dosya")
        except Exception as e:
            self._status.error(f"Uploader açılamadı: {e}")

    def _watch_upload_history(self, status_path: str, files_count: int, label: str):
        """Manuel upload'ın sonucunu geçmişe yazar. Monitor penceresinden
        bağımsız App-level izleyici — pencere kapatılsa bile süreç bitince
        (done/failed ya da beklenmedik kapanma) kayıt düşer."""
        def poll():
            state, completed = "", 0
            try:
                if os.path.exists(status_path):
                    with open(status_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    state = data.get("state", "")
                    completed = len(data.get("completed", []))
            except Exception:
                pass
            if state in ("done", "failed") or not self._upload_in_progress():
                final = state if state in ("done", "failed") else "yarıda"
                append_history({"time": time.time(), "source": "manuel",
                                "label": label, "files": files_count,
                                "completed": completed, "state": final})
                self._refresh_resume_upload_button()
                return
            self.after(2000, poll)
        self.after(2000, poll)

    def _queue_history(self, name: str, status_path: str, state: str):
        """Kuyruktaki bir projenin upload sonucunu geçmişe yazar."""
        completed, total = 0, 0
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            completed = len(data.get("completed", []))
            total = int(data.get("total", 0) or 0)
        except Exception:
            pass
        append_history({"time": time.time(), "source": "kuyruk", "label": name,
                        "files": total, "completed": completed, "state": state})

    def _cancel_steam_community_upload(self):
        """Çalışan uploader sürecini sonlandırır (tarayıcı + Playwright kapanır)."""
        proc = getattr(self, "_upload_proc", None)
        if proc is None or proc.poll() is not None:
            self._status.set("İptal edilecek aktif upload yok", C_DIM, C_DIM)
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            self._status.set("Upload iptal edildi", C_ERROR, C_ERROR)
        except Exception as e:
            self._status.error(f"İptal edilemedi: {e}")
        finally:
            self._refresh_resume_upload_button()

    def _resume_steam_community_upload(self):
        manifest, status_path = self._last_upload_paths()
        if not os.path.exists(manifest):
            self._status.error("Devam için manifest bulunamadı")
            return
        try:
            with open(manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
            files = [item["path"] for item in data.get("files", []) if os.path.exists(item.get("path", ""))]
            completed = []
            if os.path.exists(status_path):
                with open(status_path, "r", encoding="utf-8") as f:
                    status = json.load(f)
                if status.get("state") == "done":
                    self._status.ok("Son upload zaten tamamlanmış")
                    self._refresh_resume_upload_button()
                    return
                completed = status.get("completed", [])
            remaining = [p for p in files if p not in completed]
        except Exception as e:
            self._status.error(f"Devam bilgisi okunamadı: {e}")
            return
        if not remaining:
            self._status.ok("Devam edecek dosya yok")
            self._refresh_resume_upload_button()
            return
        self._status.set(f"{len(remaining)} dosya ile devam ediliyor", C_ACCENT, C_ACCENT)
        self._run_steam_community_upload(remaining)

    # ── Toplu upload kuyruğu (birden fazla proje sırayla) ─
    def _start_project_queue(self, project_names: list[str]):
        if self._splitting or getattr(self, "_queue_running", False):
            self._status.error("Bir işlem zaten sürüyor")
            return
        projects = load_projects()
        entries = [(n, projects[n]) for n in project_names if n in projects]
        if not entries:
            self._status.error("Kuyruğa proje seçilmedi")
            return

        names_list = "\n".join(f"• {n}" for n, _ in entries)
        warn = ""
        if self._cfg.get("steam_community_auto_submit"):
            warn = ("\n\nUYARI: 'Otomatik submit' açık — her proje gözetimsiz "
                     "olarak Steam'e gönderilecek.")
        if not messagebox.askyesno(
                "Toplu Upload Kuyruğu",
                f"{len(entries)} proje sırayla bölünüp Steam Community'ye "
                f"yüklenecek:\n\n{names_list}{warn}\n\nDevam edilsin mi?"):
            return

        self._splitting = True
        self._queue_running = True
        self._queue_cancelled = False
        self._queue_win = self._build_queue_window(len(entries))
        self._process_queue_item(entries, 0)

    def _build_queue_window(self, total: int):
        win = ctk.CTkToplevel(self)
        win.title("Toplu Upload Kuyruğu")
        win.geometry("520x420")
        win.configure(fg_color=C_BG1)

        ctk.CTkLabel(win, text="Toplu Upload Kuyruğu",
                     font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=16, pady=(16, 4))
        win._status_lbl = ctk.CTkLabel(
            win, text="Başlıyor...", font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
            text_color=C_ACCENT)
        win._status_lbl.pack(anchor="w", padx=16, pady=(0, 8))

        win._bar = ctk.CTkProgressBar(win, width=480, progress_color=C_ACCENT, fg_color=C_BG4)
        win._bar.pack(fill="x", padx=16, pady=(0, 10))
        win._bar.set(0)

        def cancel():
            self._queue_cancelled = True
            self._cancel_steam_community_upload()
            win._status_lbl.configure(text="İptal ediliyor...", text_color=C_ERROR)

        # Buton önce (side="bottom") paketlenir ki pencere kısa kalsa da
        # sabit yerini korusun; log kutusu ancak KALAN alanı doldurur
        # (aksi halde pack, sığmayan son elemanı sessizce gizler).
        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        AnimButton(btns, text="İptal Et", height=32, text_color=C_ERROR,
                   command=cancel).pack(fill="x")

        win._log_box = Text(win, bg=C_BG2, fg=C_TEXT, insertbackground=C_ACCENT,
                            font=("Consolas", 9), wrap="word", relief="flat",
                            padx=10, pady=10)
        win._log_box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        win._log_box.configure(state="disabled")
        return win

    def _queue_log(self, msg: str):
        win = getattr(self, "_queue_win", None)
        if not win or not win.winfo_exists():
            return
        win._log_box.configure(state="normal")
        win._log_box.insert("end", msg + "\n")
        win._log_box.see("end")
        win._log_box.configure(state="disabled")

    def _queue_finish(self, cancelled: bool):
        self._splitting = False
        self._queue_running = False
        win = getattr(self, "_queue_win", None)
        if win and win.winfo_exists():
            if cancelled:
                win._status_lbl.configure(text="İptal edildi", text_color=C_ERROR)
            else:
                win._status_lbl.configure(text="Kuyruk tamamlandı", text_color=C_SUCCESS)
                win._bar.set(1.0)
        if not cancelled:
            self._notify_attention()
        if cancelled:
            self._status.error("Toplu upload kuyruğu iptal edildi")
        else:
            self._status.ok("Toplu upload kuyruğu tamamlandı")

    def _process_queue_item(self, entries: list, index: int):
        total = len(entries)
        if self._queue_cancelled or index >= total:
            self._queue_finish(self._queue_cancelled)
            return

        name, data = entries[index]
        win = self._queue_win
        win._bar.set(index / total)
        win._status_lbl.configure(text=f"[{index + 1}/{total}] {name} — bölünüyor...")
        self._queue_log(f"[{index + 1}/{total}] {name}: bölme başladı")

        if "input_dir" in data and os.path.isdir(data["input_dir"]):
            exts = (".png", ".jpg", ".jpeg", ".webp", ".gif")
            file_paths = [os.path.join(data["input_dir"], f)
                          for f in os.listdir(data["input_dir"])
                          if f.lower().endswith(exts)]
        else:
            file_paths = [pp for pp in data.get("input_paths", []) if os.path.isfile(pp)]

        if not file_paths:
            self._queue_log(f"[{index + 1}/{total}] {name}: giriş dosyası bulunamadı, atlanıyor")
            self.after(200, lambda: self._process_queue_item(entries, index + 1))
            return

        tmpl = next((t for t in TEMPLATES if t["name"] == data.get("template_name")), None) \
            or self.template
        outdir = data.get("output_dir") or self.output_dir
        # Proje kaydedilirken dondurulmuş efekt ayarları varsa onları kullan
        # (yoksa eski davranış: o anki global ayarlar)
        cfg = self._cfg
        effects = data.get("effects")
        if isinstance(effects, dict):
            cfg = {**self._cfg,
                   **{k: v for k, v in effects.items() if k in PROFILE_KEYS and v is not None}}

        def worker():
            created, errors = [], []
            # Toplu Böl'deki çakışma korumasının aynısı: aynı stem'e sahip
            # farklı kaynaklar (foto.png + foto.jpg) birbirinin çıktısını ezmesin.
            seen_stems = {}
            for path in file_paths:
                try:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    key = stem.lower()
                    count = seen_stems.get(key, 0)
                    seen_stems[key] = count + 1
                    override = stem if count == 0 else f"{stem}_{count + 1}"
                    created.extend(process_image(path, outdir, tmpl, cfg,
                                                 name_override=override))
                except Exception as e:
                    errors.append(f"{os.path.basename(path)}: {e}")
            self.after(0, lambda: self._queue_after_split(entries, index, created, errors, data, outdir))

        threading.Thread(target=worker, daemon=True).start()

    def _queue_after_split(self, entries, index, created, errors, data, outdir):
        if self._queue_cancelled:
            self._queue_finish(True)
            return
        name, _ = entries[index]
        total = len(entries)
        if not created:
            self._queue_log(f"[{index + 1}/{total}] {name}: bölme başarısız "
                            f"({len(errors)} hata), atlanıyor")
            self.after(200, lambda: self._process_queue_item(entries, index + 1))
            return
        self._queue_log(f"[{index + 1}/{total}] {name}: {len(created)} parça oluşturuldu")
        self._queue_win._status_lbl.configure(
            text=f"[{index + 1}/{total}] {name} — upload başlıyor...")

        cfg_for_manifest = dict(self._cfg)
        if data.get("steam_community_upload_url"):
            cfg_for_manifest["steam_community_upload_url"] = data["steam_community_upload_url"]

        try:
            manifest = build_steam_upload_manifest(created, cfg_for_manifest, outdir, None)
        except Exception as e:
            self._queue_log(f"[{index + 1}/{total}] {name}: manifest hatası: {e}")
            self.after(200, lambda: self._process_queue_item(entries, index + 1))
            return

        status_path = upload_status_path(manifest)
        if os.path.exists(status_path):
            try:
                os.remove(status_path)
            except Exception:
                pass

        uploader = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_community_uploader.py")
        try:
            self._upload_proc = subprocess.Popen(
                [sys.executable, uploader, "--manifest", manifest],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                creationflags=0,
            )
        except Exception as e:
            self._queue_log(f"[{index + 1}/{total}] {name}: uploader başlatılamadı: {e}")
            self.after(200, lambda: self._process_queue_item(entries, index + 1))
            return

        self._queue_log(f"[{index + 1}/{total}] {name}: upload başladı")
        # Uploader'ın kendi elle-gönderim beklemesi 30 dk; kuyruk ona pay
        # bırakıp 35 dk'da keser (yoksa süreç çöktüğünde/tarayıcı elle
        # kapatıldığında kuyruk sonsuza kadar poll ederdi).
        deadline = time.monotonic() + 35 * 60
        self._queue_poll_upload(entries, index, status_path, deadline)

    def _queue_poll_upload(self, entries, index, status_path, deadline):
        if self._queue_cancelled:
            self._queue_finish(True)
            return
        name, _ = entries[index]
        total = len(entries)
        try:
            if os.path.exists(status_path):
                with open(status_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = data.get("state", "running")
                if state == "done":
                    self._queue_log(f"[{index + 1}/{total}] {name}: upload tamamlandı")
                    self._queue_history(name, status_path, "done")
                    self.after(300, lambda: self._process_queue_item(entries, index + 1))
                    return
                if state == "failed":
                    self._queue_log(f"[{index + 1}/{total}] {name}: upload başarısız")
                    self._queue_history(name, status_path, "failed")
                    self.after(300, lambda: self._process_queue_item(entries, index + 1))
                    return
        except Exception:
            pass

        # Uploader süreci status'u done/failed yapmadan öldüyse (çökme,
        # tarayıcının elle kapatılması) beklemeye devam etme.
        if not self._upload_in_progress():
            self._queue_log(f"[{index + 1}/{total}] {name}: uploader beklenmedik "
                            f"şekilde kapandı, sıradakine geçiliyor")
            self._queue_history(name, status_path, "yarıda")
            self.after(300, lambda: self._process_queue_item(entries, index + 1))
            return
        if time.monotonic() > deadline:
            self._queue_log(f"[{index + 1}/{total}] {name}: upload 35 dk içinde "
                            f"bitmedi, iptal edilip sıradakine geçiliyor")
            self._cancel_steam_community_upload()
            self._queue_history(name, status_path, "yarıda")
            self.after(300, lambda: self._process_queue_item(entries, index + 1))
            return
        self.after(1000, lambda: self._queue_poll_upload(entries, index, status_path, deadline))

    def _open_upload_monitor(self, status_path: str, file_paths: list[str]):
        win = ctk.CTkToplevel(self)
        win.title("Steam Upload Durumu")
        win.geometry("560x420")
        win.configure(fg_color=C_BG1)

        title = ctk.CTkLabel(win, text="Steam Upload Durumu",
                             font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
                             text_color=C_TEXT)
        title.pack(anchor="w", padx=16, pady=(16, 4))

        state_lbl = ctk.CTkLabel(win, text="Başlatılıyor...",
                                 font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                                 text_color=C_ACCENT)
        state_lbl.pack(anchor="w", padx=16, pady=(0, 8))

        bar = ctk.CTkProgressBar(win, width=520,
                                 progress_color=C_ACCENT,
                                 fg_color=C_BG4)
        bar.pack(fill="x", padx=16, pady=(0, 10))
        bar.set(0)

        log_box = Text(win, bg=C_BG2, fg=C_TEXT, insertbackground=C_ACCENT,
                       font=("Consolas", 9), wrap="word", relief="flat",
                       padx=10, pady=10)
        log_box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        log_box.insert("1.0", "Uploader bekleniyor...\n")
        log_box.configure(state="disabled")

        def set_log(lines):
            log_box.configure(state="normal")
            log_box.delete("1.0", "end")
            log_box.insert("1.0", "\n".join(lines) + ("\n" if lines else ""))
            log_box.see("end")
            log_box.configure(state="disabled")

        def poll():
            try:
                if os.path.exists(status_path):
                    with open(status_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    total = int(data.get("total", len(file_paths)) or len(file_paths) or 1)
                    completed = len(data.get("completed", []))
                    current = int(data.get("current", 0) or 0)
                    state = data.get("state", "running")
                    current_name = os.path.basename(data.get("current_file", ""))
                    failed = data.get("failed", [])
                    progress = min(1.0, max(0.0, completed / total))
                    bar.set(progress)
                    msg = f"{completed}/{total} tamamlandı"
                    if current_name:
                        msg += f" · şu an: {current_name}"
                    if state == "done":
                        msg = f"Tamamlandı · {completed}/{total}"
                        state_lbl.configure(text=msg, text_color=C_SUCCESS)
                        self._status.ok("Steam upload tamamlandı")
                        self._refresh_resume_upload_button()
                    elif state == "failed":
                        state_lbl.configure(text=f"Hata · {current_name}", text_color=C_ERROR)
                        self._status.error("Steam upload hata verdi")
                        self._refresh_resume_upload_button()
                    elif state == "waiting":
                        state_lbl.configure(text=f"Onay bekliyor · {current}/{total} · {current_name}", text_color=C_ACCENT)
                    else:
                        state_lbl.configure(text=msg, text_color=C_ACCENT)

                    lines = []
                    for ev in data.get("events", []):
                        lines.append(ev.get("message", ""))
                    if failed:
                        lines.append("")
                        lines.append("Hatalar:")
                        for item in failed:
                            lines.append(f"- {os.path.basename(item.get('path', ''))}: {item.get('error', '')}")
                    set_log(lines)
                    if state in ("done", "failed"):
                        return
            except Exception as e:
                state_lbl.configure(text=f"Durum okunamadı: {e}", text_color=C_ERROR)
            win.after(1000, poll)

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=(0, 12))
        AnimButton(btns, text="Status Dosyasını Aç", height=32,
                   command=lambda: self._open_file(status_path)
                   ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        AnimButton(btns, text="İptal Et", height=32, text_color=C_ERROR,
                   command=self._cancel_steam_community_upload
                   ).pack(side="left", fill="x", expand=True, padx=6)
        AnimButton(btns, text="Kapat", height=32,
                   command=win.destroy).pack(side="left", fill="x", expand=True, padx=(6, 0))

        poll()

    # ── Steam / Notlar ────────────────────────────────────
    def _open_steam_artwork(self):
        try:
            from pynput import mouse as pm, keyboard as pk
            global F12_ARMED
            F12_ARMED = True
            webbrowser.open("https://steamcommunity.com/sharedfiles/edititem/767/3/")
            kb = pk.Controller()
            def on_click(x, y, button, pressed):
                global F12_ARMED
                if pressed and str(button) == "Button.right" and F12_ARMED:
                    F12_ARMED = False
                    kb.press(pk.Key.f12); kb.release(pk.Key.f12)
                    return False
            threading.Thread(
                target=lambda: pm.Listener(on_click=on_click).start(),
                daemon=True).start()
            self._status.set("Steam sayfası açıldı", C_SUCCESS, C_SUCCESS)
        except ImportError:
            webbrowser.open("https://steamcommunity.com/sharedfiles/edititem/767/3/")
            self._status.set("Steam sayfası açıldı (pynput yok, F12 trick devre dışı)",
                             C_DIM, C_DIM)

    def _open_gif_maker(self):
        gif_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "GIF", "gif.py")
        if not os.path.exists(gif_script):
            self._status.error("gif.py bulunamadı")
            return
        args = [sys.executable, gif_script]
        # Şu an yüklü dosya varsa GIF Maker'a önceden yüklenmiş şekilde aç
        if self.current_path and os.path.isfile(self.current_path):
            args.append(self.current_path)
        try:
            subprocess.Popen(args, creationflags=0)
            self._status.set("GIF Maker açıldı", C_SUCCESS, C_SUCCESS)
        except Exception as e:
            self._status.error(f"Açılamadı: {e}")

    def _copy_clipboard(self, text: str, label: str = "Kod"):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._status.set(f"{label} panoya kopyalandı", C_SUCCESS, C_SUCCESS)


# ==========================================================
#   HEADLESS (EXE — sürükle-bırak)
# ==========================================================

def headless_run(target):
    default_tmpl = TEMPLATES[0]
    if os.path.isfile(target):
        outdir = os.path.join(os.path.dirname(target), "output")
        process_image(target, outdir, default_tmpl)
    else:
        outdir = os.path.join(target, "output")
        process_folder(target, outdir, default_tmpl)
    _log.info(f"[DONE] Çıktı: {outdir}")
    open_folder(outdir)


# ==========================================================
#   MAIN
# ==========================================================

def main():
    if getattr(sys, "frozen", False) and len(sys.argv) > 1:
        t = sys.argv[1]
        if os.path.exists(t):
            headless_run(t)
            return
    # Dev/normal çalıştırmada bir dosya argümanı verilirse (ör. GIF Maker'dan
    # "Steam Splitter'da Aç"), GUI'yi o dosya yüklü şekilde aç.
    preload = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    app = App(preload_path=preload)
    app.mainloop()


if __name__ == "__main__":
    main()
