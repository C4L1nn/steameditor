import os
import sys
import json
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

from tkinter import filedialog, messagebox, colorchooser, Text, Toplevel, Canvas, BooleanVar, StringVar
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
    apply_border_fx,
    find_gifsicle,
    list_border_templates,
    open_folder,
    optimize_gif_file,
    patch_gif_trailing_byte,
    patch_png_last_byte,
    process_folder,
    process_image,
    render_template_preview,
    resize_cover,
    split_gif_frames,
    template_output_summary,
)

from config import (
    PROFILE_KEYS,
    STEAM_CONSOLE_SNIPPETS,
    STEAM_DIRECT_UPLOAD_NOTE,
    STEAM_HELPER_LINKS,
    STEAM_PUBLISHED_FILE_DETAILS_URL,
    STEAM_UPLOAD_STEPS,
    TEMPLATES,
    TEMPLATE_SNIPPET_HINTS,
    _CONFIG_FILE,
    _PRESETS_FILE,
    _masked_key,
    build_steam_upload_manifest,
    fetch_steam_published_file_details,
    get_template_console_snippet,
    load_config,
    load_custom_presets,
    load_profiles,
    load_projects,
    save_config,
    save_custom_presets,
    save_profiles,
    save_projects,
    steam_api_config_errors,
    upload_status_path,
)

F12_ARMED = False  # tek seferlik F12 tetikçisi


def make_ctk_image(img: Image.Image, size: tuple[int, int] | None = None) -> ctk.CTkImage:
    """PIL görselini CustomTkinter HighDPI uyumlu görsele çevirir."""
    if size is None:
        size = img.size
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


def manual_crop_with_template(master, img_path: str, outdir: str, template: dict):
    """
    Manuel crop modu:
    - Kullanıcı sadece İLK parçanın alanını seçer.
    - Diğer parçalar şablon genişliklerine göre sağa doğru otomatik kesilir.
    """
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(img_path))[0]
    prefix = template.get("prefix", "parca")
    mode = template["mode"]

    # GIF ise burada animasyonlu işlemek istemiyoruz, uyarı verip çıkalım
    if img_path.lower().endswith(".gif"):
        messagebox.showinfo("Bilgi", "Manuel crop şu an sadece statik görsellerde aktif. GIF için otomatik bölme kullan.")
        return []

    # Tüm parçaları tek listede tut
    if mode == "uniform":
        pw = template["width"] // template["parts"]
        # Dinamik yükseklik: otomatik bölme ile tutarlı olması için
        # resmin gerçek boyutuna göre hesapla
        img_temp = Image.open(img_path)
        orig_w, orig_h = img_temp.size
        target_w = template["width"]
        aspect_ratio = orig_h / orig_w if orig_w else 1.0
        ph = int(target_w * aspect_ratio)
        img_temp.close()
        parts_info = [{"width": pw, "height": ph} for _ in range(template["parts"])]
    elif mode == "multi":
        parts_info = template["parts"]
    else:  # single
        parts_info = [{"width": template["width"], "height": template["height"]}]

    img = Image.open(img_path).convert("RGBA")
    img_w, img_h = img.size

    # Sadece ilk parça için kullanıcıdan seçim al
    first = parts_info[0]
    tw = first["width"]
    th = first["height"]
    title = f"Başlangıç - {tw}x{th} alanını seç (ENTER ile onayla)"
    dlg = FixedCropDialog(master, img, tw, th, title=title)
    bbox = dlg.get_bbox()
    if not bbox:
        return []

    x1, y1, x2, y2 = bbox
    base_x = x1
    base_y = y1

    created = []
    cur_x = base_x

    for idx, part in enumerate(parts_info, start=1):
        pw = part["width"]
        ph = part["height"]

        px1 = cur_x
        py1 = base_y

        # Taşma kontrolü (sağ kenar / alt kenar)
        if px1 + pw > img_w:
            px1 = max(0, img_w - pw)
        if py1 + ph > img_h:
            py1 = max(0, img_h - ph)

        px2 = px1 + pw
        py2 = py1 + ph

        piece = img.crop((px1, py1, px2, py2))
        fname = f"{prefix}_{base}_{idx:02}.png"
        full = os.path.join(outdir, fname)
        piece.save(full)

        if template.get("patch"):
            patch_png_last_byte(full)

        created.append(full)
        cur_x += pw  # sonraki parçayı sağa kaydır

    return created


# ==========================================================
#   GUI — Carbon × Steam Turuncu (customtkinter)
# ==========================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Renk Paleti ─────────────────────────────────────────────
C_BG0    = "#080808"
C_BG1    = "#0d0d0d"
C_BG2    = "#141414"
C_BG3    = "#1c1c1c"
C_BG4    = "#242424"
C_BG5    = "#2c2c2c"
C_BORDER = "#2e2e2e"
C_ACCENT = "#f97316"
C_ACC_DK = "#c2570b"
C_ACC_LT = "#fb923c"
C_ACC_DIM= "#f9731620"
C_TEXT   = "#f0f0f0"
C_DIM    = "#6b6b6b"
C_HINT   = "#3a3a3a"
C_SUCCESS= "#22c55e"
C_SUCC_DK= "#166534"
C_ERROR  = "#ef4444"
C_INDIGO = "#6366f1"
C_CARD_SEL = "#2a2018"   # seçili şablon kartı için sıcak tonlu arka plan


# ── Renk Araçları ───────────────────────────────────────────
def _h2r(h):
    h = h.lstrip("#")[:6]
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _r2h(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))

def lerp(c1, c2, t):
    r1,g1,b1 = _h2r(c1);  r2,g2,b2 = _h2r(c2)
    return _r2h(r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t)


# ── AnimButton ──────────────────────────────────────────────
class AnimButton(ctk.CTkButton):
    """Hover girişi/çıkışında smooth renk geçişi."""
    _N = 12; _MS = 10

    def __init__(self, master, nc=C_BG3, hc=C_BG5,
                 ac=C_ACCENT, ahc=C_ACC_LT,
                 variant="default", **kw):
        self._nc  = nc if variant != "accent" else ac
        self._hc  = hc if variant != "accent" else ahc
        self._t   = 0.0
        self._aid = None
        kw.setdefault("corner_radius", 10)
        kw.setdefault("border_width", 0)
        kw.setdefault("text_color", C_TEXT)
        kw.setdefault("font", ctk.CTkFont("Segoe UI", 13, weight="bold"))
        super().__init__(master, fg_color=self._nc,
                         hover_color=self._hc, **kw)
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _anim(self, target):
        if self._aid:
            try: self.after_cancel(self._aid)
            except: pass
        delta = (target - self._t) / self._N
        def tick(n=self._N):
            self._t = max(0.0, min(1.0, self._t + delta))
            try:
                self.configure(fg_color=lerp(self._nc, self._hc, self._t))
            except: return
            if n > 1:
                self._aid = self.after(self._MS, tick, n-1)
            else:
                self._t = target
        tick()

    def _enter(self, _=None): self._anim(1.0)
    def _leave(self, _=None): self._anim(0.0)


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
            pw = t["width"] // t["parts"]
            base = f"{t['parts']} parça · {pw}px × dinamik"
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
                 on_open_file, on_copy_path, on_delete_file, **kw):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=C_BG2,
                         border_color=C_ACCENT, **kw)
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

        # Thumbnail şeridi
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            orientation="horizontal",
            scrollbar_button_color=C_BG4,
            scrollbar_button_hover_color=C_ACCENT)
        self._scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def load(self, file_paths: list):
        """Parça dosyalarını yükleyip thumbnail olarak göster."""
        # Önceki içeriği temizle
        for w in self._scroll.winfo_children():
            w.destroy()
        self._tk_imgs.clear()
        self._file_paths = list(file_paths)

        n = len(file_paths)
        self._title_lbl.configure(
            text=f"✂  {n} parça oluşturuldu")

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

        # hint
        hint = ctk.CTkLabel(self, text="Scroll → zoom   |   Orta tık sürükle → pan   |   Sol tık → kareyi taşı   |   Enter → onayla",
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
        x1 = max(0, (sw - tw) / 2)
        y1 = max(0, (sh - th) / 2)
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


# ── SettingsPage ────────────────────────────────────────────
class SettingsPage(ctk.CTkFrame):
    """Ayarlar / Efektler / Şablonlar / Profiller / Steam API / Notlar'ı TEK
    sayfada birleştirir (sol sekme listesi). Eskiden her biri ayrı bir pop-up
    pencereydi; artık ana pencerenin içeriği bu sayfayla değişir, hiçbir
    yeni OS penceresi açılmaz. Her sekme açılışta sıfırdan kurulur (eski
    pop-up'ların her açılışta taze veriyle kurulması gibi)."""

    TABS = [
        ("Genel", "⚙"),
        ("Efektler", "🎨"),
        ("Şablonlar", "🧩"),
        ("Profiller", "🗂"),
        ("Projeler", "📁"),
        ("Steam API", "☁"),
        ("Notlar", "📋"),
    ]

    def __init__(self, master, app, on_back, **kw):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=C_BG2, border_color=C_BORDER, **kw)
        self.app = app
        self._on_back = on_back
        self._current_tab = None
        self._nav_buttons = {}
        self._notes_txt = None
        self._notes_path = os.path.join(os.path.dirname(__file__), "steam_notes.txt")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Üst başlık + Geri
        hdr = ctk.CTkFrame(self, fg_color=C_BG3, corner_radius=0, height=44)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="⚙  Ayarlar",
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color=C_TEXT).pack(side="left", padx=14)
        AnimButton(hdr, text="← Geri",
                   nc=C_BG3, hc=C_BG4,
                   height=28, corner_radius=6,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_DIM,
                   command=self._back).pack(side="right", padx=10, pady=8)

        # Sol sekme listesi
        nav = ctk.CTkFrame(self, fg_color=C_BG1, width=152, corner_radius=0)
        nav.grid(row=1, column=0, sticky="nsw")
        nav.grid_propagate(False)
        for name, icon in self.TABS:
            btn = ctk.CTkButton(
                nav, text=f"{icon}  {name}", anchor="w",
                height=38, corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                fg_color="transparent", hover_color=C_BG3,
                text_color=C_DIM,
                command=lambda n=name: self.open_tab(n))
            btn.pack(fill="x", padx=8, pady=3)
            self._nav_buttons[name] = btn

        # Sağ içerik: her açılışta sıfırdan kurulur
        self._content = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=C_BG4,
            scrollbar_button_hover_color=C_ACCENT)
        self._content.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

    def _back(self):
        self._autosave_notes()
        self._on_back()

    def open_tab(self, name):
        if self._current_tab == "Notlar" and name != "Notlar":
            self._autosave_notes()
        self._current_tab = name
        for n, btn in self._nav_buttons.items():
            active = n == name
            btn.configure(fg_color=C_BG3 if active else "transparent",
                         text_color=C_ACCENT if active else C_DIM)
        for w in self._content.winfo_children():
            w.destroy()
        builder = {
            "Genel": self._build_general,
            "Efektler": self._build_effects,
            "Şablonlar": self._build_templates,
            "Profiller": self._build_profiles,
            "Projeler": self._build_projects,
            "Steam API": self._build_steam_api,
            "Notlar": self._build_notes,
        }[name]
        builder(self._content)

    # ── Genel ──────────────────────────────────────────────
    def _build_general(self, p):
        cfg = self.app._cfg
        ctk.CTkLabel(p, text="Genel Ayarlar",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=4, pady=(4, 12))

        open_var = BooleanVar(value=bool(cfg.get("open_output_after_process", False)))
        ctk.CTkCheckBox(
            p, text="İşlem bitince çıktı klasörünü otomatik aç",
            variable=open_var, font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
        ).pack(anchor="w", padx=4, pady=8)

        upload_var = BooleanVar(value=bool(cfg.get("auto_upload", False)))
        ctk.CTkCheckBox(
            p, text="Split sonrası Steam Community upload otomasyonunu aç",
            variable=upload_var, font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
        ).pack(anchor="w", padx=4, pady=8)

        community_submit_var = BooleanVar(value=bool(cfg.get("steam_community_auto_submit", False)))
        ctk.CTkCheckBox(
            p, text="Community upload sırasında submit butonunu otomatik dene",
            variable=community_submit_var, font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
        ).pack(anchor="w", padx=4, pady=8)

        ctk.CTkLabel(p, text="STEAM COMMUNITY OTOMASYONU",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(14, 4))

        community_entries = {}
        for label, key in [
            ("Upload URL", "steam_community_upload_url"),
            ("Tarayıcı profil klasörü", "steam_community_profile_dir"),
            ("Upload başlığı", "steam_community_title_template"),
            ("Dosya seçtikten sonra bekleme (ms)", "steam_community_wait_after_upload_ms"),
        ]:
            ctk.CTkLabel(p, text=label, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(p, fg_color=C_BG3, border_color=C_BORDER,
                             text_color=C_TEXT, height=30)
            e.insert(0, str(cfg.get(key, "")))
            e.pack(fill="x", padx=4, pady=(2, 7))
            community_entries[key] = e

        ctk.CTkLabel(p, text="STEAM API",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(14, 4))

        entries = {}
        for label, key, show in [
            ("API Key", "steam_api_key", "*"),
            ("App ID", "steam_app_id", ""),
            ("Published File ID", "steam_published_file_id", ""),
        ]:
            ctk.CTkLabel(p, text=label, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(p, fg_color=C_BG3, border_color=C_BORDER,
                             text_color=C_TEXT, height=30, show=show)
            e.insert(0, cfg.get(key, ""))
            e.pack(fill="x", padx=4, pady=(2, 7))
            entries[key] = e

        ctk.CTkLabel(p, text=f"Varsayılan şablon: {cfg.get('default_preset', self.app.template['name'])}",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(8, 2))
        ctk.CTkLabel(p, text=f"Çıktı klasörü: {self.app.output_dir}",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_DIM,
                     wraplength=380, justify="left").pack(anchor="w", padx=4, pady=2)

        def save():
            cfg["open_output_after_process"] = bool(open_var.get())
            cfg["auto_upload"] = bool(upload_var.get())
            cfg["steam_community_auto_submit"] = bool(community_submit_var.get())
            for key, entry in community_entries.items():
                if key == "steam_community_title_template":
                    val = entry.get()  # görünmez/boşluklu başlığı olduğu gibi koru
                elif key == "steam_community_wait_after_upload_ms":
                    try:
                        val = int(entry.get().strip())
                    except ValueError:
                        val = 1200
                else:
                    val = entry.get().strip()
                cfg[key] = val
            for key, entry in entries.items():
                cfg[key] = entry.get().strip()
            save_config(cfg)
            self.app._status.ok("Ayarlar kaydedildi")

        AnimButton(p, text="Kaydet", variant="accent",
                   height=38, text_color=C_BG0,
                   command=save).pack(fill="x", padx=4, pady=(14, 4))

    # ── Efektler yardımcıları ────────────────────────────────
    def _slider_row(self, p, label, cfg, cfg_key, default, from_=0, to=100, fmt="{}%"):
        frame = ctk.CTkFrame(p, fg_color="transparent")
        frame.pack(fill="x", padx=4, pady=6)
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=label, font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM).pack(side="left")
        value_lbl = ctk.CTkLabel(top, text="",
                                 font=ctk.CTkFont("Consolas", 10, weight="bold"),
                                 text_color=C_ACCENT)
        value_lbl.pack(side="right")
        slider = ctk.CTkSlider(frame, from_=from_, to=to,
                               button_color=C_ACCENT, button_hover_color=C_ACC_LT,
                               progress_color=C_ACCENT, fg_color=C_BG4)
        slider.pack(fill="x", pady=(4, 0))
        raw = cfg.get(cfg_key, default)
        slider.set(int(raw) if raw is not None else default)

        def update(value):
            value_lbl.configure(text=fmt.format(int(float(value))))

        slider.configure(command=update)
        update(slider.get())
        return slider

    def _sep_line(self, p):
        ctk.CTkFrame(p, height=1, fg_color=C_BORDER).pack(fill="x", pady=(10, 10))

    # ── Efektler (Border FX + Metin Katmanı + Otomatik İyileştir) ──
    def _build_effects(self, p):
        cfg = self.app._cfg
        ctk.CTkLabel(p, text="Efektler",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=4, pady=(4, 6))
        ctk.CTkLabel(p, text="Split öncesi tüm görsele/parçaya birlikte uygulanır: "
                             "önce iyileştirme, sonra border, en üstte metin.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_DIM,
                     wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 12))

        # ── Border FX ──
        ctk.CTkLabel(p, text="BORDER FX", font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(0, 6))

        templates = list_border_templates()
        border_enabled_var = template_var = color_entry = opacity_slider = glow_slider = None

        if not templates:
            ctk.CTkLabel(p, text="Border Templates klasöründe PNG bulunamadı.",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=C_ERROR).pack(anchor="w", padx=4, pady=8)
        else:
            if cfg.get("border_fx_template") not in templates:
                cfg["border_fx_template"] = templates[0]

            border_enabled_var = BooleanVar(value=bool(cfg.get("border_fx_enabled", False)))
            ctk.CTkCheckBox(
                p, text="Border efektini aktif et",
                variable=border_enabled_var, font=ctk.CTkFont("Segoe UI", 11),
                text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
                checkmark_color=C_BG0,
            ).pack(anchor="w", padx=4, pady=(0, 12))

            ctk.CTkLabel(p, text="Template", font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=4)
            template_var = StringVar(value=cfg.get("border_fx_template", templates[0]))
            ctk.CTkOptionMenu(
                p, values=templates, variable=template_var,
                fg_color=C_BG3, button_color=C_ACCENT, button_hover_color=C_ACC_LT,
                dropdown_fg_color=C_BG3, dropdown_hover_color=C_BG4,
                text_color=C_TEXT,
                font=ctk.CTkFont("Segoe UI", 11, weight="bold")).pack(fill="x", padx=4, pady=(2, 10))

            ctk.CTkLabel(p, text="Renk (#RRGGBB)", font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=4)
            color_entry = ctk.CTkEntry(p, fg_color=C_BG3, border_color=C_BORDER,
                                       text_color=C_TEXT, height=32)
            color_entry.insert(0, cfg.get("border_fx_color", "#8B5CF6"))
            color_entry.pack(fill="x", padx=4, pady=(2, 10))

            swatches = [
                "#FF6B00", "#F97316", "#FACC15", "#22C55E",
                "#22D3EE", "#3B82F6", "#8B5CF6", "#EC4899",
                "#EF4444", "#FFFFFF", "#111827", "#94A3B8",
            ]
            swatch_f = ctk.CTkFrame(p, fg_color="transparent")
            swatch_f.pack(fill="x", padx=4, pady=(0, 10))
            preview_dot = ctk.CTkFrame(swatch_f, width=28, height=28,
                                       fg_color=cfg.get("border_fx_color", "#8B5CF6"),
                                       corner_radius=14)
            preview_dot.pack(side="left", padx=(0, 8))
            preview_dot.pack_propagate(False)

            def set_color(value):
                color_entry.delete(0, "end")
                color_entry.insert(0, value)
                preview_dot.configure(fg_color=value)

            def sync_color_preview(_=None):
                color = color_entry.get().strip()
                if len(color.lstrip("#")) in (3, 6):
                    preview_dot.configure(fg_color=color)

            def pick_any_color():
                initial = color_entry.get().strip() or "#8B5CF6"
                _, picked = colorchooser.askcolor(color=initial, title="Border rengini seç")
                if picked:
                    set_color(picked.upper())

            for color in swatches:
                ctk.CTkButton(
                    swatch_f, text="", width=24, height=24, corner_radius=12,
                    fg_color=color, hover_color=color,
                    border_width=1, border_color=C_BORDER,
                    command=lambda c=color: set_color(c)
                ).pack(side="left", padx=3)
            color_entry.bind("<KeyRelease>", sync_color_preview)

            AnimButton(p, text="Tüm renklerden seç",
                       nc=C_BG3, hc=C_BG4, height=32, text_color=C_TEXT,
                       command=pick_any_color).pack(fill="x", padx=4, pady=(0, 10))

            opacity_slider = self._slider_row(p, "Opaklik", cfg, "border_fx_opacity", 100)
            glow_slider = self._slider_row(p, "Glow", cfg, "border_fx_glow", 35)

        self._sep_line(p)

        # ── Metin Katmanı ──
        ctk.CTkLabel(p, text="METİN KATMANI", font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(0, 6))

        text_enabled_var = BooleanVar(value=bool(cfg.get("text_overlay_enabled", False)))
        ctk.CTkCheckBox(
            p, text="Metin katmanını aktif et",
            variable=text_enabled_var, font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
        ).pack(anchor="w", padx=4, pady=(0, 10))

        ctk.CTkLabel(p, text="Metin", font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM).pack(anchor="w", padx=4)
        text_entry = ctk.CTkEntry(p, fg_color=C_BG3, border_color=C_BORDER,
                                  text_color=C_TEXT, height=32,
                                  placeholder_text="Başlık / imza metni")
        text_entry.insert(0, cfg.get("text_overlay_text", ""))
        text_entry.pack(fill="x", padx=4, pady=(2, 10))

        row1 = ctk.CTkFrame(p, fg_color="transparent")
        row1.pack(fill="x", padx=4, pady=(0, 10))
        col_a = ctk.CTkFrame(row1, fg_color="transparent")
        col_a.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkLabel(col_a, text="Renk (#RRGGBB)", font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM).pack(anchor="w")
        text_color_entry = ctk.CTkEntry(col_a, fg_color=C_BG3, border_color=C_BORDER,
                                        text_color=C_TEXT, height=32)
        text_color_entry.insert(0, cfg.get("text_overlay_color", "#FFFFFF"))
        text_color_entry.pack(fill="x", pady=(2, 0))

        col_b = ctk.CTkFrame(row1, fg_color="transparent")
        col_b.pack(side="left", fill="x", expand=True, padx=(4, 0))
        ctk.CTkLabel(col_b, text="Konum", font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM).pack(anchor="w")
        position_var = StringVar(value=cfg.get("text_overlay_position", "Alt Orta"))
        ctk.CTkOptionMenu(
            col_b, values=list(_TEXT_OVERLAY_POSITIONS), variable=position_var,
            fg_color=C_BG3, button_color=C_ACCENT, button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3, dropdown_hover_color=C_BG4,
            text_color=C_TEXT, font=ctk.CTkFont("Segoe UI", 11, weight="bold")
        ).pack(fill="x", pady=(2, 0))

        text_size_slider = self._slider_row(p, "Boyut", cfg, "text_overlay_size", 6,
                                            from_=1, to=30, fmt="{}%")
        text_opacity_slider = self._slider_row(p, "Opaklik", cfg, "text_overlay_opacity", 100)

        self._sep_line(p)

        # ── Otomatik İyileştir ──
        ctk.CTkLabel(p, text="OTOMATİK İYİLEŞTİR", font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(0, 6))
        ctk.CTkLabel(p, text="Kontrast, doygunluk, parlaklık ve keskinliği tek ayarla dengeler.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_DIM,
                     wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 8))

        enhance_enabled_var = BooleanVar(value=bool(cfg.get("auto_enhance_enabled", False)))
        ctk.CTkCheckBox(
            p, text="Otomatik iyileştirmeyi aktif et",
            variable=enhance_enabled_var, font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
        ).pack(anchor="w", padx=4, pady=(0, 10))

        enhance_slider = self._slider_row(p, "Yoğunluk", cfg, "auto_enhance_intensity", 50)

        def save_all():
            if border_enabled_var is not None:
                cfg["border_fx_enabled"] = bool(border_enabled_var.get())
                cfg["border_fx_template"] = template_var.get()
                cfg["border_fx_color"] = color_entry.get().strip() or "#8B5CF6"
                cfg["border_fx_opacity"] = int(opacity_slider.get())
                cfg["border_fx_glow"] = int(glow_slider.get())
            cfg["text_overlay_enabled"] = bool(text_enabled_var.get())
            cfg["text_overlay_text"] = text_entry.get().strip()
            cfg["text_overlay_color"] = text_color_entry.get().strip() or "#FFFFFF"
            cfg["text_overlay_position"] = position_var.get()
            cfg["text_overlay_size"] = int(text_size_slider.get())
            cfg["text_overlay_opacity"] = int(text_opacity_slider.get())
            cfg["auto_enhance_enabled"] = bool(enhance_enabled_var.get())
            cfg["auto_enhance_intensity"] = int(enhance_slider.get())
            save_config(cfg)
            if self.app.current_path and os.path.isfile(self.app.current_path):
                self.app._load_preview(self.app.current_path)
            self.app._status.ok("Efektler kaydedildi")

        AnimButton(p, text="Kaydet", variant="accent",
                   height=38, text_color=C_BG0,
                   command=save_all).pack(fill="x", padx=4, pady=(14, 4))

    # ── Şablonlar ──────────────────────────────────────────
    def _build_templates(self, p):
        ctk.CTkLabel(p, text="Şablonlar",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=4, pady=(4, 10))

        # Yeni şablon oluştur
        new_card = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=10)
        new_card.pack(fill="x", padx=2, pady=(0, 14))
        ctk.CTkLabel(new_card, text="YENİ ŞABLON OLUŞTUR",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=12, pady=(10, 6))

        new_fields = {}
        row = ctk.CTkFrame(new_card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 4))
        for label, key, default in [
            ("Parça genişliği (px)", "w", "150"),
            ("Parça yüksekliği (px)", "h", "1250"),
            ("Parça sayısı", "n", "5"),
        ]:
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True, padx=3)
            ctk.CTkLabel(col, text=label, font=ctk.CTkFont("Segoe UI", 9),
                         text_color=C_DIM).pack(anchor="w")
            e = ctk.CTkEntry(col, fg_color=C_BG4, border_color=C_BORDER,
                             text_color=C_TEXT, height=30)
            e.insert(0, default)
            e.pack(fill="x", pady=(2, 0))
            new_fields[key] = e

        def create_template():
            try:
                pw = int(new_fields["w"].get())
                ph = int(new_fields["h"].get())
                cnt = int(new_fields["n"].get())
                if pw <= 0 or ph <= 0 or cnt <= 0:
                    raise ValueError
            except ValueError:
                self.app._status.error("Geçerli pozitif sayı gir")
                return
            tmpl = {
                "name": f"Özel ({pw}×{ph} ×{cnt})",
                "mode": "uniform",
                "width": pw * cnt,
                "height": ph,
                "parts": cnt,
                "patch": False,
                "prefix": "cus",
            }
            TEMPLATES.append(tmpl)
            self.app.template = tmpl
            save_custom_presets()
            self.app._rebuild_template_cards()
            self.app._status.set(f"Şablon eklendi: {tmpl['name']}", C_SUCCESS, C_SUCCESS)
            self.open_tab("Şablonlar")

        AnimButton(new_card, text="＋  Ekle",
                   variant="accent", height=32, text_color=C_BG0,
                   command=create_template).pack(fill="x", padx=10, pady=(6, 10))

        # Mevcut şablonları yönet
        ctk.CTkLabel(p, text="ŞABLONU YÖNET",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(0, 6))

        names = [t["name"] for t in TEMPLATES]
        selected = StringVar(value=self.app.template["name"])
        menu = ctk.CTkOptionMenu(
            p, values=names, variable=selected,
            fg_color=C_BG3, button_color=C_ACCENT, button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3, dropdown_hover_color=C_BG4, text_color=C_TEXT)
        menu.pack(fill="x", padx=4, pady=(0, 12))

        fields = {}
        for label, key in [
            ("Ad", "name"),
            ("Toplam genişlik", "width"),
            ("Referans yükseklik", "height"),
            ("Parça sayısı", "parts"),
            ("Prefix", "prefix"),
        ]:
            ctk.CTkLabel(p, text=label, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(p, fg_color=C_BG3, border_color=C_BORDER,
                             text_color=C_TEXT, height=30)
            e.pack(fill="x", padx=4, pady=(2, 7))
            fields[key] = e

        patch_var = BooleanVar(value=False)
        ctk.CTkCheckBox(p, text="PNG son byte patch",
                        variable=patch_var, font=ctk.CTkFont("Segoe UI", 11),
                        text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
                        checkmark_color=C_BG0).pack(anchor="w", padx=4, pady=4)

        def current_template():
            return next((t for t in TEMPLATES if t["name"] == selected.get()), None)

        def fill(_=None):
            t = current_template()
            if not t:
                return
            is_uniform = t.get("mode") == "uniform"
            for key, entry in fields.items():
                entry.configure(state="normal")
                entry.delete(0, "end")
            fields["name"].insert(0, t.get("name", ""))
            fields["width"].insert(0, str(t.get("width", "")))
            fields["height"].insert(0, str(t.get("height", "")))
            fields["parts"].insert(0, str(t.get("parts", "")) if is_uniform else "")
            fields["prefix"].insert(0, t.get("prefix", ""))
            patch_var.set(bool(t.get("patch", False)))
            state = "normal" if t.get("prefix") not in ("work", "art", "shot") and is_uniform else "disabled"
            for entry in fields.values():
                entry.configure(state=state)

        menu.configure(command=fill)
        fill()

        def set_default():
            t = current_template()
            if not t:
                return
            self.app.template = t
            self.app._cfg["default_preset"] = t["name"]
            save_config(self.app._cfg)
            self.app._sync_cards()
            self.app._status.ok("Varsayılan şablon kaydedildi")

        def save_edit():
            t = current_template()
            if not t or t.get("prefix") in ("work", "art", "shot") or t.get("mode") != "uniform":
                self.app._status.error("Sadece özel uniform şablonlar düzenlenebilir")
                return
            try:
                name = fields["name"].get().strip()
                width = int(fields["width"].get())
                height = int(fields["height"].get())
                parts = int(fields["parts"].get())
                prefix = fields["prefix"].get().strip() or "cus"
                if not name or width <= 0 or height <= 0 or parts <= 0:
                    raise ValueError
            except ValueError:
                self.app._status.error("Şablon değerleri geçersiz")
                return
            t.update({
                "name": name, "width": width, "height": height,
                "parts": parts, "patch": bool(patch_var.get()), "prefix": prefix,
            })
            save_custom_presets()
            self.app.template = t
            self.app._rebuild_template_cards()
            self.app._status.ok("Şablon güncellendi")
            self.open_tab("Şablonlar")

        def delete_template():
            t = current_template()
            if not t or t.get("prefix") in ("work", "art", "shot"):
                self.app._status.error("Yerleşik şablon silinemez")
                return
            if not messagebox.askyesno("Şablonu Sil", f"{t['name']} silinsin mi?"):
                return
            TEMPLATES.remove(t)
            if self.app.template is t or self.app.template.get("name") == t.get("name"):
                self.app.template = TEMPLATES[0]
            save_custom_presets()
            self.app._rebuild_template_cards()
            self.app._status.ok("Şablon silindi")
            self.open_tab("Şablonlar")

        btns = ctk.CTkFrame(p, fg_color="transparent")
        btns.pack(fill="x", padx=4, pady=(8, 4))
        AnimButton(btns, text="Varsayılan Yap", height=32,
                   command=set_default).pack(fill="x", pady=3)
        AnimButton(btns, text="Düzenle", variant="accent",
                   height=32, text_color=C_BG0,
                   command=save_edit).pack(fill="x", pady=3)
        AnimButton(btns, text="Sil", nc=C_BG3, hc=C_BG4,
                   height=32, text_color=C_ERROR,
                   command=delete_template).pack(fill="x", pady=3)

    # ── Profiller ──────────────────────────────────────────
    def _build_profiles(self, p):
        cfg = self.app._cfg
        ctk.CTkLabel(p, text="Profiller",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=4, pady=(4, 6))
        ctk.CTkLabel(p, text="Şablon + Border FX + upload ayarını tek profil olarak kaydet, "
                             "sonra tek tıkla uygula.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_DIM,
                     wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 12))

        # Yeni profil oluştur
        new_card = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=10)
        new_card.pack(fill="x", padx=2, pady=(0, 14))
        ctk.CTkLabel(new_card, text="MEVCUT AYARLARDAN PROFİL OLUŞTUR",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=12, pady=(10, 6))
        name_entry = ctk.CTkEntry(new_card, fg_color=C_BG4, border_color=C_BORDER,
                                  text_color=C_TEXT, height=32,
                                  placeholder_text="Profil adı (ör. Vitrin + Kırmızı Border)")
        name_entry.pack(fill="x", padx=10, pady=(0, 8))

        def create_profile():
            name = name_entry.get().strip()
            if not name:
                self.app._status.error("Profil adı gir")
                return
            profiles = load_profiles()
            profiles[name] = {"template_name": self.app.template.get("name")}
            for key in PROFILE_KEYS:
                profiles[name][key] = cfg.get(key)
            save_profiles(profiles)
            self.app._status.ok(f"Profil kaydedildi: {name}")
            self.open_tab("Profiller")

        AnimButton(new_card, text="＋  Profil Olarak Kaydet",
                   variant="accent", height=32, text_color=C_BG0,
                   command=create_profile).pack(fill="x", padx=10, pady=(0, 10))

        # Mevcut profiller
        ctk.CTkLabel(p, text="KAYITLI PROFİLLER",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(0, 6))

        profiles = load_profiles()
        if not profiles:
            ctk.CTkLabel(p, text="Henüz profil yok.",
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=4, pady=8)
            return

        def apply_profile(name, data):
            tmpl = next((t for t in TEMPLATES if t["name"] == data.get("template_name")), None)
            if tmpl:
                self.app.template = tmpl
                self.app._sync_cards()
            for key in PROFILE_KEYS:
                if key in data:
                    cfg[key] = data[key]
            save_config(cfg)
            if self.app.current_path and os.path.isfile(self.app.current_path):
                self.app._load_preview(self.app.current_path)
            note = "" if tmpl else " (şablon artık yok, atlandı)"
            self.app._status.ok(f"Profil uygulandı: {name}{note}")

        def delete_profile(name):
            if not messagebox.askyesno("Profili Sil", f"'{name}' profili silinsin mi?"):
                return
            current = load_profiles()
            current.pop(name, None)
            save_profiles(current)
            self.app._status.ok("Profil silindi")
            self.open_tab("Profiller")

        for name, data in sorted(profiles.items()):
            row = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=8)
            row.pack(fill="x", padx=2, pady=4)
            info_bits = [data.get("template_name") or "?"]
            if data.get("border_fx_enabled"):
                info_bits.append("Border FX açık")
            if data.get("text_overlay_enabled"):
                info_bits.append("Metin açık")
            if data.get("auto_enhance_enabled"):
                info_bits.append("Otomatik iyileştir açık")
            if data.get("auto_upload"):
                info_bits.append("Auto-upload")
            ctk.CTkLabel(row, text=name,
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color=C_TEXT, anchor="w").pack(anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(row, text="  ·  ".join(info_bits),
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=C_DIM, anchor="w").pack(anchor="w", padx=12, pady=(0, 6))
            btns = ctk.CTkFrame(row, fg_color="transparent")
            btns.pack(fill="x", padx=10, pady=(0, 8))
            AnimButton(btns, text="Uygula", variant="accent", height=28, text_color=C_BG0,
                       command=lambda n=name, d=data: apply_profile(n, d)
                       ).pack(side="left", fill="x", expand=True, padx=(0, 4))
            AnimButton(btns, text="Sil", nc=C_BG4, hc=C_BG5, height=28, text_color=C_ERROR,
                       command=lambda n=name: delete_profile(n)
                       ).pack(side="left", fill="x", expand=True, padx=(4, 0))

    # ── Projeler ───────────────────────────────────────────
    def _build_projects(self, p):
        ctk.CTkLabel(p, text="Projeler",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=4, pady=(4, 6))
        ctk.CTkLabel(p, text="Birden fazla Workshop öğesi üzerinde çalışıyorsan: hangi "
                             "dosya(lar)/şablon/çıktı klasörüyle kaldığını kaydet, sonra "
                             "tek tıkla o duruma geri dön.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_DIM,
                     wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 12))

        app = self.app

        # Yeni proje oluştur
        new_card = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=10)
        new_card.pack(fill="x", padx=2, pady=(0, 14))
        ctk.CTkLabel(new_card, text="MEVCUT DURUMDAN PROJE OLUŞTUR",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=12, pady=(10, 6))

        current_desc = "Giriş seçilmedi"
        if app._batch_files:
            current_desc = f"{len(app._batch_files)} dosya (toplu)"
        elif app.current_path and os.path.isdir(app.current_path):
            current_desc = f"Klasör: {os.path.basename(app.current_path)}"
        elif app.current_path and os.path.isfile(app.current_path):
            current_desc = f"Dosya: {os.path.basename(app.current_path)}"
        ctk.CTkLabel(new_card,
                     text=f"Şu an: {current_desc}  ·  {app.template.get('name', '?')}",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=C_ACCENT,
                     wraplength=400, justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        name_entry = ctk.CTkEntry(new_card, fg_color=C_BG4, border_color=C_BORDER,
                                  text_color=C_TEXT, height=32,
                                  placeholder_text="Proje adı (ör. Kılıç Modu v2)")
        name_entry.pack(fill="x", padx=10, pady=(0, 6))
        note_entry = ctk.CTkEntry(new_card, fg_color=C_BG4, border_color=C_BORDER,
                                  text_color=C_TEXT, height=32,
                                  placeholder_text="Not (opsiyonel)")
        note_entry.pack(fill="x", padx=10, pady=(0, 6))
        url_entry = ctk.CTkEntry(new_card, fg_color=C_BG4, border_color=C_BORDER,
                                 text_color=C_TEXT, height=32,
                                 placeholder_text="Bu Workshop öğesinin upload URL'i (boşsa genel ayar kullanılır)")
        url_entry.pack(fill="x", padx=10, pady=(0, 8))

        def create_project():
            name = name_entry.get().strip()
            if not name:
                app._status.error("Proje adı gir")
                return
            if not app._batch_files and not (app.current_path and
                    (os.path.isfile(app.current_path) or os.path.isdir(app.current_path))):
                app._status.error("Önce bir dosya/klasör seç")
                return
            entry = {
                "template_name": app.template.get("name"),
                "output_dir": app.output_dir,
                "note": note_entry.get().strip(),
            }
            url = url_entry.get().strip()
            if url:
                entry["steam_community_upload_url"] = url
            if app._batch_files:
                entry["input_paths"] = list(app._batch_files)
            elif os.path.isdir(app.current_path):
                entry["input_dir"] = app.current_path
            else:
                entry["input_paths"] = [app.current_path]
            pfid = app._cfg.get("steam_published_file_id", "").strip()
            if pfid:
                entry["steam_published_file_id"] = pfid
            projects = load_projects()
            projects[name] = entry
            save_projects(projects)
            app._status.ok(f"Proje kaydedildi: {name}")
            self.open_tab("Projeler")

        AnimButton(new_card, text="＋  Proje Olarak Kaydet",
                   variant="accent", height=32, text_color=C_BG0,
                   command=create_project).pack(fill="x", padx=10, pady=(0, 10))

        # Mevcut projeler
        ctk.CTkLabel(p, text="KAYITLI PROJELER",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(0, 6))

        projects = load_projects()
        if not projects:
            ctk.CTkLabel(p, text="Henüz proje yok.",
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=C_DIM).pack(anchor="w", padx=4, pady=8)
            return

        def open_project(name, data):
            if "input_dir" in data and os.path.isdir(data["input_dir"]):
                app._batch_files = None
                app.current_path = data["input_dir"]
                app._drop.reset()
            elif "input_paths" in data:
                valid = [pp for pp in data["input_paths"] if os.path.isfile(pp)]
                if len(valid) == 1:
                    app._on_file_drop(valid[0])
                elif len(valid) > 1:
                    app._on_batch_drop(valid)
                else:
                    app._status.error("Proje dosyaları artık bulunamıyor")
                    return
            tmpl = next((t for t in TEMPLATES if t["name"] == data.get("template_name")), None)
            if tmpl:
                app.template = tmpl
                app._sync_cards()
            if data.get("output_dir") and os.path.isdir(data["output_dir"]):
                app.output_dir = data["output_dir"]
                app._out_lbl.configure(text=app._short_path(app.output_dir))
            cfg_changed = False
            if data.get("steam_published_file_id"):
                app._cfg["steam_published_file_id"] = data["steam_published_file_id"]
                cfg_changed = True
            if data.get("steam_community_upload_url"):
                app._cfg["steam_community_upload_url"] = data["steam_community_upload_url"]
                cfg_changed = True
            if cfg_changed:
                save_config(app._cfg)
            note = f" — {data['note']}" if data.get("note") else ""
            app._status.ok(f"Proje açıldı: {name}{note}")

        def delete_project(name):
            if not messagebox.askyesno("Projeyi Sil", f"'{name}' projesi silinsin mi?"):
                return
            current = load_projects()
            current.pop(name, None)
            save_projects(current)
            app._status.ok("Proje silindi")
            self.open_tab("Projeler")

        # Toplu upload kuyruğu: birden fazla projeyi işaretleyip sırayla
        # böl + Steam Community'ye yükle (dış sisteme etkisi var, onay ister).
        queue_vars = {}

        def start_queue():
            selected = [n for n, v in queue_vars.items() if v.get()]
            if not selected:
                app._status.error("Kuyruğa en az bir proje seç")
                return
            app._start_project_queue(selected)

        if len(projects) > 1:
            AnimButton(p, text="🚀  Seçili Projeleri Kuyruğa Al ve Başlat",
                       variant="accent", height=34, text_color=C_BG0,
                       command=start_queue).pack(fill="x", padx=2, pady=(0, 8))

        for name, data in sorted(projects.items()):
            row = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=8)
            row.pack(fill="x", padx=2, pady=4)

            if "input_dir" in data:
                src_desc = f"Klasör: {os.path.basename(data['input_dir'])}"
            else:
                n = len(data.get("input_paths", []))
                src_desc = f"{n} dosya" if n != 1 else os.path.basename(data.get("input_paths", ["?"])[0])
            info_bits = [src_desc, data.get("template_name") or "?"]
            if data.get("steam_community_upload_url"):
                info_bits.append("özel upload URL")
            if data.get("note"):
                info_bits.append(data["note"])

            header_row = ctk.CTkFrame(row, fg_color="transparent")
            header_row.pack(fill="x", padx=12, pady=(8, 0))
            qvar = BooleanVar(value=False)
            queue_vars[name] = qvar
            if len(projects) > 1:
                ctk.CTkCheckBox(header_row, text="", variable=qvar, width=20,
                               fg_color=C_ACCENT, hover_color=C_ACC_LT,
                               checkmark_color=C_BG0).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(header_row, text=name,
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color=C_TEXT, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text="  ·  ".join(info_bits),
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=C_DIM, anchor="w", wraplength=380,
                         justify="left").pack(anchor="w", padx=12, pady=(0, 6))
            btns = ctk.CTkFrame(row, fg_color="transparent")
            btns.pack(fill="x", padx=10, pady=(0, 8))
            AnimButton(btns, text="Aç", variant="accent", height=28, text_color=C_BG0,
                       command=lambda n=name, d=data: open_project(n, d)
                       ).pack(side="left", fill="x", expand=True, padx=(0, 4))
            AnimButton(btns, text="Sil", nc=C_BG4, hc=C_BG5, height=28, text_color=C_ERROR,
                       command=lambda n=name: delete_project(n)
                       ).pack(side="left", fill="x", expand=True, padx=(4, 0))

    # ── Steam API ──────────────────────────────────────────
    def _build_steam_api(self, p):
        cfg = self.app._cfg
        ctk.CTkLabel(p, text="Steam API Kontrol",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=4, pady=(4, 6))
        ctk.CTkLabel(p, text=STEAM_DIRECT_UPLOAD_NOTE,
                     font=ctk.CTkFont("Segoe UI", 10), text_color=C_DIM,
                     wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 12))

        info = (
            f"API Key: {_masked_key(cfg.get('steam_api_key', '')) or '(boş)'}\n"
            f"App ID: {cfg.get('steam_app_id', '') or '(boş)'}\n"
            f"Published File ID: {cfg.get('steam_published_file_id', '') or '(boş)'}\n"
            f"Son çıktı: {len(self.app._last_outputs)} dosya"
        )
        ctk.CTkLabel(p, text=info, font=ctk.CTkFont("Consolas", 11),
                     text_color=C_TEXT, justify="left").pack(anchor="w", padx=4, pady=8)

        output = Text(p, bg=C_BG2, fg=C_TEXT, insertbackground=C_ACCENT,
                      font=("Consolas", 10), wrap="word", relief="flat",
                      padx=10, pady=10, height=9)
        output.pack(fill="both", expand=True, padx=4, pady=8)
        output.insert("1.0", "Hazır.\n")
        output.configure(state="disabled")

        def write(msg):
            output.configure(state="normal")
            output.insert("end", msg + "\n")
            output.see("end")
            output.configure(state="disabled")

        def validate():
            write("Config kontrol ediliyor...")
            errors = steam_api_config_errors(cfg)
            if errors:
                write("Eksik: " + ", ".join(errors))
                return
            try:
                details = fetch_steam_published_file_details(
                    cfg.get("steam_published_file_id", "").strip())
                if not details:
                    write("Published file bulunamadı veya cevap boş.")
                    return
                title = details.get("title", "(başlıksız)")
                app_id = details.get("consumer_app_id", "?")
                write(f"Bulundu: {title} | consumer_app_id={app_id}")
            except Exception as e:
                write(f"Steam API hatası: {e}")

        def prepare_manifest():
            files = self.app._last_outputs
            if not files:
                write("Son çıktı listesi boş; önce split işlemi yap.")
                return
            ok, msg = self.app._prepare_steam_api_upload(files)
            write(msg)
            if not ok:
                write("Direkt upload için SteamCMD veya Steamworks SDK entegrasyonu gerekir.")

        def run_community():
            files = self.app._last_outputs
            if not files:
                write("Son çıktı listesi boş; önce split işlemi yap.")
                return
            self.app._run_steam_community_upload(files)
            write("Steam Community uploader başlatıldı.")

        btns = ctk.CTkFrame(p, fg_color="transparent")
        btns.pack(fill="x", padx=4, pady=(0, 4))
        AnimButton(btns, text="API Doğrula", variant="accent",
                   height=34, text_color=C_BG0,
                   command=validate).pack(side="left", fill="x", expand=True, padx=(0, 6))
        AnimButton(btns, text="Manifest Hazırla",
                   height=34,
                   command=prepare_manifest).pack(side="left", fill="x", expand=True, padx=6)
        AnimButton(btns, text="Community Upload",
                   height=34,
                   command=run_community).pack(side="left", fill="x", expand=True, padx=6)
        AnimButton(btns, text="Ayarlar",
                   height=34,
                   command=lambda: self.open_tab("Genel")).pack(side="left", fill="x", expand=True, padx=(6, 0))

    # ── Notlar ─────────────────────────────────────────────
    def _autosave_notes(self):
        if self._notes_txt is None:
            return
        try:
            with open(self._notes_path, "w", encoding="utf-8") as f:
                f.write(self._notes_txt.get("1.0", "end-1c"))
        except Exception:
            pass
        self._notes_txt = None

    def _build_notes(self, p):
        ctk.CTkLabel(p, text="📋  Steam Yardımcı Paneli",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=4, pady=(4, 10))

        tabs = ctk.CTkTabview(
            p, fg_color=C_BG1, height=560,
            segmented_button_selected_color=C_ACCENT,
            segmented_button_selected_hover_color=C_ACC_LT,
            segmented_button_unselected_color=C_BG3,
            segmented_button_unselected_hover_color=C_BG4,
            text_color=C_TEXT,
        )
        tabs.pack(fill="both", expand=True, padx=0, pady=(0, 8))
        helper_tab = tabs.add("Yardımcı")
        notes_tab = tabs.add("Notlar")

        helper = ctk.CTkScrollableFrame(
            helper_tab, fg_color=C_BG2, corner_radius=10,
            scrollbar_button_color=C_BG4, scrollbar_button_hover_color=C_ACCENT)
        helper.pack(fill="both", expand=True, padx=4, pady=4)

        ctk.CTkLabel(helper, text="CONSOLE KODLARI",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=14, pady=(14, 6))

        preferred = TEMPLATE_SNIPPET_HINTS.get(self.app.template.get("mode"))

        for title, snippet in STEAM_CONSOLE_SNIPPETS:
            is_preferred = title == preferred
            row = ctk.CTkFrame(helper,
                               fg_color=C_BG4 if is_preferred else C_BG3,
                               border_width=2 if is_preferred else 0,
                               border_color=C_ACCENT, corner_radius=8)
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=title, font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color=C_TEXT, anchor="w").pack(
                             side="left", fill="x", expand=True, padx=10, pady=8)
            AnimButton(row, text="Kopyala",
                       nc=C_ACCENT, hc=C_ACC_LT, variant="accent",
                       height=28, corner_radius=6,
                       font=ctk.CTkFont("Segoe UI", 10),
                       text_color=C_BG0,
                       command=lambda s=snippet, t=title: self.app._copy_clipboard(s, t)
                       ).pack(side="right", padx=8, pady=6)

        ctk.CTkLabel(helper, text="HIZLI LİNKLER",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=14, pady=(14, 6))

        links_grid = ctk.CTkFrame(helper, fg_color="transparent")
        links_grid.pack(fill="x", padx=10, pady=(0, 8))
        links_grid.grid_columnconfigure((0, 1), weight=1)
        for i, (title, url) in enumerate(STEAM_HELPER_LINKS):
            AnimButton(links_grid, text=title,
                       nc=C_BG3, hc=C_BG4, height=32, corner_radius=8,
                       font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT,
                       command=lambda u=url: webbrowser.open(u)
                       ).grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)

        ctk.CTkLabel(helper, text="UPLOAD CHECKLIST",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=14, pady=(14, 6))

        for step in STEAM_UPLOAD_STEPS:
            ctk.CTkCheckBox(
                helper, text=step, font=ctk.CTkFont("Segoe UI", 11),
                text_color=C_TEXT, fg_color=C_ACCENT, hover_color=C_ACC_LT,
                checkmark_color=C_BG0,
            ).pack(anchor="w", padx=16, pady=4)

        txt = Text(notes_tab, bg=C_BG2, fg=C_TEXT, insertbackground=C_ACCENT,
                   font=("Consolas", 10), wrap="word", undo=True,
                   relief="flat", padx=12, pady=12,
                   selectbackground=C_ACCENT, selectforeground=C_BG0)
        txt.pack(fill="both", expand=True, padx=4, pady=4)

        if os.path.exists(self._notes_path):
            try:
                with open(self._notes_path, "r", encoding="utf-8") as f:
                    txt.insert("1.0", f.read())
            except Exception:
                pass
        self._notes_txt = txt

        def save_now():
            self._autosave_notes()
            self._notes_txt = txt  # sekmede kalmaya devam ediyor
            self.app._status.ok("Notlar kaydedildi")

        AnimButton(notes_tab, text="Kaydet",
                   nc=C_ACCENT, hc=C_ACC_LT, variant="accent",
                   height=32, text_color=C_BG0,
                   command=save_now).pack(fill="x", pady=(6, 0))


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
                print(f"[DND] tkdnd yüklenemedi, sürükle-bırak devre dışı: {e}")
        self.title("Steam Splitter PRO")
        self.geometry("1340x840")
        self.minsize(1040, 700)
        self.configure(fg_color=C_BG1)

        self.current_path = None
        self._batch_files = None         # çoklu seçim: belirli dosya listesi (klasörden ayrı)
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

        if preload_path and os.path.isfile(preload_path):
            # Pencere tam çizilmeden önizleme boyutlandırması yanlış çıkmasın diye
            # mainloop başladıktan sonraya ertele.
            self.after(200, lambda: self._on_file_drop(preload_path))

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

    # ── SIDEBAR ───────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=260, fg_color=C_BG2,
                          corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(1, weight=1)  # kaydırılabilir gövde tüm boşluğu alır

        # Logo — sabit, kaymaz
        logo_f = ctk.CTkFrame(sb, fg_color="transparent")
        logo_f.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 4))
        ctk.CTkLabel(logo_f, text="⚡",
                     font=ctk.CTkFont("Segoe UI Emoji", 26),
                     text_color=C_ACCENT).pack(side="left")
        name_f = ctk.CTkFrame(logo_f, fg_color="transparent")
        name_f.pack(side="left", padx=6)
        ctk.CTkLabel(name_f, text="Steam Splitter",
                     font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
                     text_color=C_TEXT).pack(anchor="w")
        ctk.CTkLabel(name_f, text="PRO  v2.0",
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

        AnimButton(tools_f, text="🎨  Efektler",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=lambda: self._open_settings_page("Efektler")
                   ).pack(fill="x", pady=2)

        AnimButton(tools_f, text="☁  Steam API Kontrol",
                   nc=C_BG3, hc=C_BG4,
                   height=32, corner_radius=8,
                   font=ctk.CTkFont("Segoe UI", 11),
                   text_color=C_TEXT,
                   command=lambda: self._open_settings_page("Steam API")
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

        # Manuel crop ayrı satır
        btn_f2 = ctk.CTkFrame(main, fg_color="transparent")
        btn_f2.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        btn_f2.grid_columnconfigure(0, weight=1)

        AnimButton(btn_f2,
                   text="🎯  Manuel Crop (Oto-Parça)",
                   nc=C_BG3, hc=C_INDIGO,
                   height=36,
                   font=ctk.CTkFont("Segoe UI", 12),
                   command=self._manual_crop
                   ).grid(row=0, column=0, sticky="ew")

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
        self._batch_files = valid
        self.current_path = valid[0]
        self._remember_input_dir(os.path.dirname(valid[0]))
        self._load_preview(valid[0])
        self._status.set(f"{len(valid)} dosya seçildi (toplu bölme)", C_TEXT, C_SUCCESS)

    def _load_preview(self, path):
        try:
            img = Image.open(path)
            if hasattr(img, "n_frames") and img.n_frames > 1:
                img.seek(0)
            preview = render_template_preview(img, self.template, self._cfg)
            batch_count = len(self._batch_files) if self._batch_files else 0
            self._drop.show_image(preview, template_output_summary(img, self.template),
                                  batch_count=batch_count)
        except Exception as e:
            self._status.error(f"Önizleme hatası: {e}")

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
        self._splitting = True
        self._status.busy("Bölünüyor...")

        def worker():
            try:
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
        self._split_prev.load(file_paths)
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
        dlg.geometry("400x130")
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

        def worker():
            # Aynı isim gövdesine (stem) sahip FARKLI kaynak dosyalar aynı
            # çıktı adını üretip birbirinin üstüne yazmasın diye say.
            seen_stems = {}
            for i, path in enumerate(file_paths, 1):
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
                dlg.after(0, lambda i=i, n=fname: _upd(i, n))
            dlg.after(0, _done)

        def _upd(i, name):
            bar.set(i / total)
            lbl.configure(text=f"{name}  ({i}/{total})")

        def _done():
            self._splitting = False
            dlg.destroy()
            if errors:
                self._status.error(
                    f"{len(created_all)} parça, {len(errors)} hata")
            else:
                self._status.ok(
                    f"{len(created_all)} parça oluşturuldu ({total} dosya) ✓")
            self._show_split_preview(created_all)
            # Raporu hata VEYA çakışma-yeniden-adlandırma varsa göster
            if errors or renamed:
                self._show_batch_report(total, created_all, errors, renamed)

        threading.Thread(target=worker, daemon=True).start()

    def _manual_crop(self):
        if not self.current_path or os.path.isdir(self.current_path):
            self._status.error("Manuel crop için tek resim seç")
            return
        created = manual_crop_with_template(
            self, self.current_path, self.output_dir, self.template)
        if created:
            self._status.ok(f"Manuel: {len(created)} parça oluşturuldu ✓")
            self._show_split_preview(created)

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

    def _steam_api_after_split(self, file_paths: list[str]):
        def worker():
            ok, msg = self._prepare_steam_api_upload(file_paths)
            color = C_SUCCESS if ok else C_ERROR
            self.after(0, lambda: self._status.set(msg, color, color))
        threading.Thread(target=worker, daemon=True).start()

    def _prepare_steam_api_upload(self, file_paths: list[str]):
        errors = steam_api_config_errors(self._cfg)
        if errors:
            return False, "Steam API config eksik: " + ", ".join(errors)
        try:
            details = fetch_steam_published_file_details(
                self._cfg.get("steam_published_file_id", "").strip())
            if details and str(details.get("consumer_app_id", "")) not in ("", str(self._cfg.get("steam_app_id", "")).strip()):
                return False, "Published file app id config ile eşleşmiyor"
        except Exception as e:
            return False, f"Steam API doğrulama hatası: {e}"

        manifest = build_steam_upload_manifest(file_paths, self._cfg, self.output_dir, self.template)
        return False, f"Direkt Web API upload yok; manifest hazır: {os.path.basename(manifest)}"

    def _prepare_steam_community_manifest(self, file_paths: list[str]) -> str:
        return build_steam_upload_manifest(file_paths, self._cfg, self.output_dir, self.template)

    def _run_steam_community_upload(self, file_paths: list[str] | None = None):
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
        except Exception as e:
            self._status.error(f"Uploader açılamadı: {e}")

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
        cfg = self._cfg

        def worker():
            created, errors = [], []
            for path in file_paths:
                try:
                    created.extend(process_image(path, outdir, tmpl, cfg))
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
        self._queue_poll_upload(entries, index, status_path)

    def _queue_poll_upload(self, entries, index, status_path):
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
                    self.after(300, lambda: self._process_queue_item(entries, index + 1))
                    return
                if state == "failed":
                    self._queue_log(f"[{index + 1}/{total}] {name}: upload başarısız")
                    self.after(300, lambda: self._process_queue_item(entries, index + 1))
                    return
        except Exception:
            pass
        self.after(1000, lambda: self._queue_poll_upload(entries, index, status_path))

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
            "GİF", "gif.py")
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
    print("[DONE] Çıktı:", outdir)
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
