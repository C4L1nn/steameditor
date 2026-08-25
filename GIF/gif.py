import os
import sys
import subprocess
import tempfile
import threading
import platform
import shutil
import time
import random
import json
import math
import uuid

# customtkinter otomatik kurulum
try:
    import customtkinter as ctk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from tkinter import filedialog, messagebox, StringVar, IntVar, BooleanVar
from PIL import Image, ImageTk, ImageEnhance, ImageFilter, ImageDraw, ImageChops, ImageSequence

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Windows'ta ffmpeg/gifsicle çağrılarında konsol penceresi flaş'ını engelle
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

# ── Araç yolları ──────────────────────────────────────────
def _find_tool(name: str) -> str | None:
    """Sistemde bir komut satırı aracı bul.
    Önce PATH'a bakar, sonra yaygın Windows kurulum klasörlerini tarar,
    sonra script klasörüne ve üstüne bakar.
    Bulamazsa None döner.
    """
    # 1. PATH kontrolü
    found = shutil.which(name)
    if found:
        return found

    exe = name if name.endswith(".exe") else name + ".exe"

    # 2. Yaygın Windows ffmpeg kurulum yerleri
    common = [
        rf"C:\ffmpeg\bin\{exe}",
        rf"C:\Program Files\ffmpeg\bin\{exe}",
        rf"C:\Program Files (x86)\ffmpeg\bin\{exe}",
        rf"C:\tools\ffmpeg\bin\{exe}",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "bin", exe),
        os.path.join(os.environ.get("USERPROFILE",  ""), "ffmpeg", "bin", exe),
        os.path.join(os.environ.get("USERPROFILE",  ""), "Downloads", "ffmpeg", "bin", exe),
    ]
    for p in common:
        if p and os.path.isfile(p):
            return p

    # 3. Script klasörü ve üst klasörler
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for folder in [script_dir,
                   os.path.dirname(script_dir),
                   os.path.join(script_dir, "bin"),
                   os.path.join(script_dir, "ffmpeg", "bin"),
                   os.path.join(os.path.dirname(script_dir), "bin"),
                   os.path.join(os.path.dirname(script_dir), "ffmpeg", "bin")]:
        candidate = os.path.join(folder, exe)
        if os.path.isfile(candidate):
            return candidate

    return None

FFMPEG_FOUND   = _find_tool("ffmpeg")
FFPROBE_FOUND  = _find_tool("ffprobe")
GIFSICLE_FOUND = _find_tool("gifsicle")

FFMPEG   = FFMPEG_FOUND   or "ffmpeg"
FFPROBE  = FFPROBE_FOUND  or "ffprobe"
GIFSICLE = GIFSICLE_FOUND or "gifsicle"

# ffmpeg yoksa kullanıcıya uyarı gösterilecek (App.__init__ içinde)
FFMPEG_MISSING = FFMPEG_FOUND is None
GIFSICLE_MISSING = GIFSICLE_FOUND is None

QUALITY_PROFILES = {
    "Steam hızlı": {
        "fmt": "GIF",
        "width": "480",
        "fps": 15,
        "lossy": 25,
        "colors": "64",
        "sharpen": True,
        "smooth": False,
    },
    "Steam kaliteli": {
        "fmt": "GIF",
        "width": "720",
        "fps": 24,
        "lossy": 12,
        "colors": "128",
        "sharpen": True,
        "smooth": False,
    },
    "Küçük dosya": {
        "fmt": "GIF",
        "width": "480",
        "fps": 12,
        "lossy": 35,
        "colors": "64",
        "sharpen": False,
        "smooth": False,
    },
    "Ezgif benzeri": {
        "fmt": "GIF",
        "width": "480",
        "fps": 15,
        "lossy": 110,
        "colors": "64",
        "sharpen": True,
        "smooth": False,
    },
    "WebP HD": {
        "fmt": "WebP",
        "width": "1080",
        "fps": 30,
        "lossy": 0,
        "colors": "256",
        "sharpen": True,
        "smooth": False,
    },
}

EFFECT_PRESETS = {
    "Efekt yok": "none",
    "Neon mor kenarlik": "neon",
    "Karanlik glow": "dark_glow",
    "VHS / scanline": "vhs",
    "Sinema vignette": "cinema",
    "Purple Soul": "purple_soul",
    "Blue Lightning": "blue_lightning",
    "Blood Curse": "blood_curse",
    "Ice Mist": "ice_mist",
    "Golden Divine": "golden_divine",
    "Cyber Glitch": "cyber_glitch",
    "VHS Horror": "vhs_horror",
    "Inferno Ember": "inferno_ember",
}

EFFECT_DESCRIPTIONS = {
    "Efekt yok": "Temiz",
    "Neon mor kenarlik": "Mor neon",
    "Karanlik glow": "Koyu aura",
    "VHS / scanline": "Retro çizgi",
    "Sinema vignette": "Cinematic",
    "Purple Soul": "Ruh parçacığı",
    "Blue Lightning": "Mavi şimşek",
    "Blood Curse": "Kırmızı lanet",
    "Ice Mist": "Buz sisi",
    "Golden Divine": "Altın bloom",
    "Cyber Glitch": "RGB glitch",
    "VHS Horror": "Karanlık VHS",
    "Inferno Ember": "Alev parçacığı",
}

EFFECT_GROUPS = {
    "Look": ["Efekt yok", "Sinema vignette", "Karanlik glow"],
    "Aura": ["Neon mor kenarlik", "Purple Soul", "Blue Lightning", "Golden Divine"],
    "Dark": ["Blood Curse", "VHS Horror", "Inferno Ember"],
    "FX": ["Ice Mist", "Cyber Glitch", "VHS / scanline"],
}

USER_PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "effect_presets.json")
BORDER_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Border Templates")
BORDER_TEMPLATE_NONE = "Yok"

# ── Renk Paleti (Carbon × Turuncu — editor.py ile aynı) ──
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
C_TEXT   = "#f0f0f0"
C_DIM    = "#6b6b6b"
C_HINT   = "#3a3a3a"
C_SUCCESS= "#22c55e"
C_ERROR  = "#ef4444"
C_INDIGO = "#6366f1"


# ── Renk yardımcıları ─────────────────────────────────────
def _h2r(h):
    h = h.lstrip("#")[:6]
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _r2h(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))

def lerp(c1, c2, t):
    r1,g1,b1 = _h2r(c1); r2,g2,b2 = _h2r(c2)
    return _r2h(r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t)


# ── AnimButton ────────────────────────────────────────────
class AnimButton(ctk.CTkButton):
    _N = 12; _MS = 10
    def __init__(self, master, nc=C_BG3, hc=C_BG5,
                 variant="default", **kw):
        self._nc  = nc if variant != "accent" else C_ACCENT
        self._hc  = hc if variant != "accent" else C_ACC_LT
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


# ── SliderRow ─────────────────────────────────────────────
class SliderRow(ctk.CTkFrame):
    """Etiket + slider + değer göstergesi."""
    def __init__(self, master, label, from_, to, init, fmt="{}", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._fmt = fmt

        ctk.CTkLabel(self, text=label,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")

        self._val_lbl = ctk.CTkLabel(
            self, text=fmt.format(init),
            font=ctk.CTkFont("Consolas", 11, weight="bold"),
            text_color=C_ACCENT, width=40, anchor="e")
        self._val_lbl.pack(side="right")

        self.slider = ctk.CTkSlider(
            self, from_=from_, to=to,
            progress_color=C_ACCENT,
            button_color=C_ACCENT,
            button_hover_color=C_ACC_LT,
            fg_color=C_BG4,
            command=self._on_change)
        self.slider.pack(side="left", fill="x", expand=True, padx=8)
        self.slider.set(init)
        self._cb = None

    def _on_change(self, val):
        self._val_lbl.configure(text=self._fmt.format(int(val)))
        if self._cb:
            self._cb(int(val))

    def get(self): return int(self.slider.get())
    def set(self, val):
        self.slider.set(val)
        self._on_change(val)
    def bind_change(self, fn): self._cb = fn


# ── VideoPreview ──────────────────────────────────────────
class VideoPreview(ctk.CTkFrame):
    def __init__(self, master, on_file, **kw):
        kw.setdefault("corner_radius", 12)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=C_BG2,
                         border_color=C_BORDER, **kw)
        self._on_file = on_file
        self._pulse_t = 0.0
        self._pulse_dir = 1
        self._pulse_id = None
        self._source_img = None    # ham kaynak karesi (efekt pipeline'ının girdisi)
        self._display_img = None   # ekranda gösterilen (efektli WYSIWYG) kare
        self._info_text = ""

        self._idle = ctk.CTkFrame(self, fg_color="transparent")

        badge = ctk.CTkFrame(self._idle, width=78, height=78,
                             corner_radius=39, fg_color=C_BG3)
        badge.pack(pady=(8, 14))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="🎬",
                     font=ctk.CTkFont("Segoe UI Emoji", 32),
                     text_color=C_ACC_LT).pack(expand=True)

        ctk.CTkLabel(self._idle, text="Video / görsel sürükle",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color=C_TEXT).pack()
        ctk.CTkLabel(self._idle, text="veya tıklayıp dosya seç",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM).pack(pady=(3, 14))

        pill = ctk.CTkFrame(self._idle, fg_color=C_BG3, corner_radius=10)
        pill.pack()
        ctk.CTkLabel(pill, text="MP4  ·  MOV  ·  AVI  ·  MKV",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(padx=12, pady=5)

        self._idle.pack(expand=True)

        self._thumb_lbl = ctk.CTkLabel(self, text="", fg_color="transparent")

        self._info_lbl = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont("Consolas", 9),
            text_color=C_DIM)
        self.bind("<Configure>", lambda _: self._render_image(), add="+")

        def _bind_click(w):
            try: w.bind("<Button-1>", self._pick, add="+")
            except Exception: pass
            for c in w.winfo_children():
                _bind_click(c)
        _bind_click(self)

        self._pulse()

    def _pulse(self):
        self._pulse_t += 0.03 * self._pulse_dir
        if self._pulse_t >= 1.0: self._pulse_t = 1.0; self._pulse_dir = -1
        elif self._pulse_t <= 0.0: self._pulse_t = 0.0; self._pulse_dir = 1
        try:
            self.configure(border_color=lerp(C_BORDER, C_HINT, self._pulse_t))
        except: return
        self._pulse_id = self.after(55, self._pulse)

    def _pick(self, _=None):
        p = filedialog.askopenfilename(
            filetypes=[
                ("Video / Görsel", "*.mp4;*.mov;*.avi;*.mkv;*.webm;*.gif;*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("Video", "*.mp4;*.mov;*.avi;*.mkv;*.webm"),
                ("Görsel", "*.gif;*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
            ])
        if p: self._on_file(p)

    def show(self, thumb_path, info_text):
        if self._pulse_id:
            try: self.after_cancel(self._pulse_id)
            except: pass
        self._idle.pack_forget()
        try:
            self._source_img = Image.open(thumb_path).convert("RGB")
            self._display_img = None  # efekt önizlemesi gelene dek ham kare
            self._thumb_lbl.pack(expand=True, fill="both", padx=10, pady=(10, 4))
            self._render_image()
        except Exception:
            ctk.CTkLabel(self, text="🎬  Önizleme yüklendi",
                         text_color=C_DIM).pack(pady=20)

        self._info_lbl.configure(text=info_text)
        self._info_lbl.pack(pady=(0, 10))
        self.configure(border_color=C_ACCENT)

    def show_effect_image(self, pil_img):
        """Efektli WYSIWYG kareyi ana tuvale basar — kaynak kare
        (get_source_image) efekt pipeline'ının girdisi olarak korunur."""
        self._display_img = pil_img
        self._render_image()

    def _render_image(self):
        img = self._display_img or self._source_img
        if img is None:
            return
        w = max(260, self.winfo_width() - 24)
        h = max(220, self.winfo_height() - 54)
        img = img.copy()
        img.thumbnail((w, h), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        self._thumb_lbl.configure(image=tk_img, text="")
        self._thumb_lbl._image = tk_img

    def get_source_image(self):
        return self._source_img.copy() if self._source_img is not None else None


# ── StatusBar ─────────────────────────────────────────────
class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("corner_radius", 8)
        super().__init__(master, fg_color=C_BG2, height=34, **kw)
        self.pack_propagate(False)
        self._dot = ctk.CTkLabel(self, text="●",
                                 font=ctk.CTkFont("Segoe UI", 10),
                                 text_color=C_SUCCESS, width=18)
        self._dot.pack(side="left", padx=(10, 3))
        self._lbl = ctk.CTkLabel(self, text="Hazır",
                                 font=ctk.CTkFont("Segoe UI", 10),
                                 text_color=C_DIM, anchor="w")
        self._lbl.pack(side="left", fill="x", expand=True)
        self._size_lbl = ctk.CTkLabel(self, text="",
                                      font=ctk.CTkFont("Consolas", 11,
                                                       weight="bold"),
                                      text_color=C_ACCENT)
        self._size_lbl.pack(side="right", padx=12)
        self._fade_id = None

    def set(self, msg, color=C_TEXT, dot=C_SUCCESS, reset=True):
        if self._fade_id:
            try: self.after_cancel(self._fade_id)
            except: pass
        self._dot.configure(text_color=dot)
        self._lbl.configure(text=msg, text_color=color)
        if reset:
            self._fade_id = self.after(5000, lambda: self._lbl.configure(
                text="Hazır", text_color=C_DIM))

    def set_size(self, txt): self._size_lbl.configure(text=txt)
    def busy(self, msg): self.set(msg, C_ACCENT, C_ACCENT, reset=False)
    def ok(self, msg): self.set(msg, C_SUCCESS, C_SUCCESS)
    def error(self, msg): self.set(msg, C_ERROR, C_ERROR)


# ── GifMaker ──────────────────────────────────────────────
class GifMaker(ctk.CTk):

    def __init__(self, preload_path=None):
        super().__init__()
        self.title("SplitForge GIF Studio")
        self.geometry("1080x680")
        self.minsize(900, 580)
        self.configure(fg_color=C_BG1)
        # Ana uygulamayla aynı marka/ikon (repo kökündeki app_icon.*)
        _root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        try:
            self.iconbitmap(os.path.join(_root, "app_icon.ico"))
        except Exception:
            pass
        try:
            self._icon_photo = ImageTk.PhotoImage(
                Image.open(os.path.join(_root, "app_icon.png")))
            self.iconphoto(True, self._icon_photo)
        except Exception:
            pass

        self.video_path     = None
        self.source_kind    = "video"
        self.video_width    = 720
        self.video_height   = 1280
        self.video_duration = 3.0
        self._est_thread    = None
        self._est_cancel    = threading.Event()
        self._est_after_id  = None
        self._fx_after_id   = None
        self._effect_buttons = {}
        self._effect_gallery_open = False
        self._effect_gallery_toggle = None
        self._effect_gallery_body = None
        self._user_presets = _load_effect_presets()
        self._show_before_var = BooleanVar(value=False)
        self._last_est_bytes = None
        self._last_output_path = None

        self._build()

        if preload_path and os.path.isfile(preload_path):
            self.after(200, lambda: self._load_media(preload_path))

    # ── Layout ────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # Sol: önizleme + dönüştür
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(14, 6), pady=14)
        left.grid_rowconfigure(0, weight=0)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Başlık — ana uygulamayla aynı marka
        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew")
        try:
            _logo_src = Image.open(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "app_icon.png"))
            self._hdr_logo = ctk.CTkImage(light_image=_logo_src,
                                          dark_image=_logo_src, size=(26, 26))
            ctk.CTkLabel(hdr, text="", image=self._hdr_logo).pack(side="left")
        except Exception:
            ctk.CTkLabel(hdr, text="🎬",
                         font=ctk.CTkFont("Segoe UI Emoji", 22),
                         text_color=C_ACCENT).pack(side="left")
        ctk.CTkLabel(hdr, text="SplitForge",
                     font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
                     text_color=C_TEXT).pack(side="left", padx=(6, 4))
        ctk.CTkLabel(hdr, text="GIF Studio · video → GIF/WebP",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C_DIM).pack(side="left")

        # TEK büyük önizleme: efekt uygulanmış WYSIWYG kare burada görünür
        # (eskiden kaynak + efekt iki ayrı küçük paneldi — birleştirildi)
        self._preview = VideoPreview(left, self._load_media)
        self._preview.grid(row=1, column=0, sticky="nsew", pady=(10, 8))

        # Kaynak seç + Before/After tek satırda
        src_row = ctk.CTkFrame(left, fg_color="transparent")
        src_row.grid(row=2, column=0, sticky="ew")
        src_row.grid_columnconfigure(0, weight=1)
        AnimButton(src_row, text="📂  Video / Görsel Seç",
                   nc=C_BG3, hc=C_BG4,
                   height=38, command=self._pick_media
                   ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkCheckBox(
            src_row, text="Before / After",
            variable=self._show_before_var,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT,
            fg_color=C_ACCENT,
            hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
            command=self._trigger_effect_preview
        ).grid(row=0, column=1)

        # Dönüştür butonu
        self._btn_convert = AnimButton(
            left,
            text="▶  Dönüştür",
            nc=C_ACCENT, hc=C_ACC_LT,
            variant="accent",
            height=46,
            text_color=C_BG0,
            command=self._convert)
        self._btn_convert.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        # Son çıktıyı doğrudan Steam Splitter'da aç (dönüştürme bitince aktifleşir)
        self._btn_send_to_splitter = AnimButton(
            left, text="✂  Steam Splitter'da Aç (son çıktı)",
            nc=C_BG3, hc=C_BG4,
            height=34,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_DIM,
            command=self._send_to_splitter)
        self._btn_send_to_splitter.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self._btn_send_to_splitter.configure(state="disabled")

        # Status
        self._status = StatusBar(left)
        self._status.grid(row=5, column=0, sticky="ew", pady=(8, 0))

        # Sağ: ayarlar
        right = ctk.CTkScrollableFrame(
            self, fg_color=C_BG2,
            corner_radius=12,
            scrollbar_button_color=C_BG4,
            scrollbar_button_hover_color=C_BG5)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 14), pady=14)

        self._build_settings(right)

    def _sep(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color=C_BORDER
                     ).pack(fill="x", padx=6, pady=8)

    def _section(self, p, title, first=False):
        """Ayar sütununda numaralı bölüm başlığı — düz kontrol listesi yerine
        gruplu, taranabilir bir düzen için."""
        ctk.CTkFrame(p, height=1, fg_color=C_BORDER
                     ).pack(fill="x", padx=6, pady=(2 if first else 14, 0))
        ctk.CTkLabel(p, text=title,
                     font=ctk.CTkFont("Segoe UI", 10, weight="bold"),
                     text_color=C_ACCENT
                     ).pack(anchor="w", padx=14, pady=(8, 6))

    def _build_settings(self, p):
        self._section(p, "①  ÇIKTI", first=True)

        # Hazır kalite profilleri
        prof_f = ctk.CTkFrame(p, fg_color="transparent")
        prof_f.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(prof_f, text="Profil",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        self._profile_var = StringVar(value="Steam kaliteli")
        prof = ctk.CTkOptionMenu(
            prof_f,
            values=list(QUALITY_PROFILES.keys()),
            variable=self._profile_var,
            fg_color=C_BG3,
            button_color=C_ACCENT,
            button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3,
            dropdown_hover_color=C_BG4,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            command=self._apply_profile)
        prof.pack(side="left", fill="x", expand=True)

        # Format
        fmt_f = ctk.CTkFrame(p, fg_color="transparent")
        fmt_f.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(fmt_f, text="Format",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        self._fmt_var = StringVar(value="GIF")
        seg = ctk.CTkSegmentedButton(
            fmt_f, values=["GIF", "WebP"],
            variable=self._fmt_var,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACC_LT,
            unselected_color=C_BG3,
            unselected_hover_color=C_BG4,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            command=self._on_setting_change)
        seg.pack(side="left", fill="x", expand=True)

        # Genişlik
        res_f = ctk.CTkFrame(p, fg_color="transparent")
        res_f.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(res_f, text="Genişlik",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        self._res_var = StringVar(value="720")
        seg2 = ctk.CTkSegmentedButton(
            res_f, values=["480", "720", "1080"],
            variable=self._res_var,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACC_LT,
            unselected_color=C_BG3,
            unselected_hover_color=C_BG4,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            command=self._on_setting_change)
        seg2.pack(side="left", fill="x", expand=True)

        # FPS slider
        self._fps_row = SliderRow(p, "FPS", 5, 60, 20, fmt="{} fps")
        self._fps_row.pack(fill="x", padx=12, pady=4)
        self._fps_row.bind_change(lambda _: self._on_setting_change())

        # Lossy slider
        self._lossy_row = SliderRow(p, "Lossy", 0, 200, 10, fmt="{}")
        self._lossy_row.pack(fill="x", padx=12, pady=4)
        self._lossy_row.bind_change(lambda _: self._on_setting_change())

        # Renk modu
        color_f = ctk.CTkFrame(p, fg_color="transparent")
        color_f.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(color_f, text="Renkler",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        self._color_var = StringVar(value="64")
        seg3 = ctk.CTkSegmentedButton(
            color_f, values=["64", "128", "256"],
            variable=self._color_var,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACC_LT,
            unselected_color=C_BG3,
            unselected_hover_color=C_BG4,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            command=self._on_setting_change)
        seg3.pack(side="left", fill="x", expand=True)

        self._section(p, "②  EFEKT")

        effect_f = ctk.CTkFrame(p, fg_color="transparent")
        effect_f.pack(fill="x", padx=12, pady=(4, 4))
        ctk.CTkLabel(effect_f, text="Efekt",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        self._effect_var = StringVar(value="Neon mor kenarlik")
        effect_menu = ctk.CTkOptionMenu(
            effect_f,
            values=list(EFFECT_PRESETS.keys()),
            variable=self._effect_var,
            fg_color=C_BG3,
            button_color=C_ACCENT,
            button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3,
            dropdown_hover_color=C_BG4,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
            command=self._on_effect_menu_change)
        effect_menu.pack(side="left", fill="x", expand=True)

        gallery = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=10)
        gallery.pack(fill="x", padx=12, pady=(8, 6))
        self._effect_gallery_toggle = ctk.CTkButton(
            gallery,
            text="> Efekt galerisi",
            height=34,
            corner_radius=8,
            fg_color=C_BG4,
            hover_color=C_BG5,
            border_width=1,
            border_color=C_BORDER,
            text_color=C_TEXT,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 10, weight="bold"),
            command=self._toggle_effect_gallery)
        self._effect_gallery_toggle.pack(fill="x", padx=8, pady=8)
        self._effect_gallery_body = ctk.CTkFrame(gallery, fg_color="transparent")
        # Not: bu etiket _effect_gallery_body'nin İÇİNE konur (gallery'nin
        # doğrudan çocuğu değil) — aksi halde _sync_effect_gallery_visibility
        # içindeki gizleme döngüsü bunu da gizler ve hiç görünmezdi.
        ctk.CTkLabel(self._effect_gallery_body, text="EFEKT GALERİSİ",
                     font=ctk.CTkFont("Segoe UI", 8, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=10, pady=(8, 4))
        for group, names in EFFECT_GROUPS.items():
            ctk.CTkLabel(self._effect_gallery_body, text=group,
                         font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                         text_color=C_ACCENT).pack(anchor="w", padx=10, pady=(4, 2))
            row = ctk.CTkFrame(self._effect_gallery_body, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=(0, 4))
            for name in names:
                btn = ctk.CTkButton(
                    row,
                    text=f"{name}\n{EFFECT_DESCRIPTIONS.get(name, '')}",
                    height=44,
                    corner_radius=8,
                    fg_color=C_BG4,
                    hover_color=C_BG5,
                    border_width=1,
                    border_color=C_BORDER,
                    text_color=C_TEXT,
                    font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                    command=lambda n=name: self._select_effect(n))
                btn.pack(side="left", fill="x", expand=True, padx=3)
                self._effect_buttons[name] = btn
        self._sync_effect_gallery_visibility()

        self._border_row = SliderRow(p, "Kenarlik", 0, 18, 5, fmt="{} px")
        self._border_row.pack(fill="x", padx=12, pady=4)
        self._border_row.bind_change(lambda _: self._on_setting_change())

        templates = [BORDER_TEMPLATE_NONE] + _list_border_templates()
        self._border_template_var = StringVar(value=templates[0])
        template_f = ctk.CTkFrame(p, fg_color="transparent")
        template_f.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(template_f, text="Template",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        ctk.CTkOptionMenu(
            template_f,
            values=templates,
            variable=self._border_template_var,
            fg_color=C_BG3,
            button_color=C_ACCENT,
            button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3,
            dropdown_hover_color=C_BG4,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 10, weight="bold"),
            command=self._on_setting_change
        ).pack(side="left", fill="x", expand=True)

        self._glow_row = SliderRow(p, "Glow", 0, 100, 45, fmt="{}%")
        self._glow_row.pack(fill="x", padx=12, pady=4)
        self._glow_row.bind_change(lambda _: self._on_setting_change())

        self._intensity_row = SliderRow(p, "Intensity", 0, 100, 75, fmt="{}%")
        self._intensity_row.pack(fill="x", padx=12, pady=4)
        self._intensity_row.bind_change(lambda _: self._on_setting_change())

        self._bloom_row = SliderRow(p, "Bloom", 0, 100, 55, fmt="{}%")
        self._bloom_row.pack(fill="x", padx=12, pady=4)
        self._bloom_row.bind_change(lambda _: self._on_setting_change())

        self._vignette_row = SliderRow(p, "Vignette", 0, 100, 45, fmt="{}%")
        self._vignette_row.pack(fill="x", padx=12, pady=4)
        self._vignette_row.bind_change(lambda _: self._on_setting_change())

        self._particle_row = SliderRow(p, "Particles", 0, 100, 45, fmt="{}%")
        self._particle_row.pack(fill="x", padx=12, pady=4)
        self._particle_row.bind_change(lambda _: self._on_setting_change())

        self._section(p, "③  PRESETLER")

        preset_card = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=10)
        preset_card.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(preset_card, text="Efekt + çıktı ayarlarını isimli preset olarak sakla",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C_DIM).pack(anchor="w", padx=10, pady=(8, 4))
        self._user_preset_var = StringVar(value=self._first_user_preset_name())
        self._user_preset_menu = ctk.CTkOptionMenu(
            preset_card,
            values=self._user_preset_names(),
            variable=self._user_preset_var,
            fg_color=C_BG4,
            button_color=C_ACCENT,
            button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3,
            dropdown_hover_color=C_BG4,
            text_color=C_TEXT,
            font=ctk.CTkFont("Segoe UI", 10, weight="bold"))
        self._user_preset_menu.pack(fill="x", padx=8, pady=(0, 6))

        preset_btn_row = ctk.CTkFrame(preset_card, fg_color="transparent")
        preset_btn_row.pack(fill="x", padx=8, pady=(0, 8))
        AnimButton(preset_btn_row, text="Yükle", height=30,
                   nc=C_BG4, hc=C_BG5,
                   command=self._apply_user_preset).pack(side="left", fill="x", expand=True, padx=(0, 4))
        AnimButton(preset_btn_row, text="Kaydet", height=30,
                   nc=C_ACCENT, hc=C_ACC_LT,
                   variant="accent",
                   text_color=C_BG0,
                   command=self._save_user_preset).pack(side="left", fill="x", expand=True, padx=(4, 0))

        self._section(p, "④  GELİŞMİŞ")

        # Süre
        dur_f = ctk.CTkFrame(p, fg_color="transparent")
        dur_f.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(dur_f, text="Süre (sn)",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        self._dur_entry = ctk.CTkEntry(
            dur_f, fg_color=C_BG3, border_color=C_BORDER,
            text_color=C_TEXT, height=30,
            placeholder_text="boş = tüm video")
        self._dur_entry.pack(side="left", fill="x", expand=True)
        self._dur_entry.bind("<FocusOut>", lambda _: self._on_setting_change())

        target_f = ctk.CTkFrame(p, fg_color="transparent")
        target_f.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(target_f, text="Hedef MB",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM, width=80, anchor="w"
                     ).pack(side="left")
        self._target_mb_entry = ctk.CTkEntry(
            target_f, fg_color=C_BG3, border_color=C_BORDER,
            text_color=C_TEXT, height=30,
            placeholder_text="boş = serbest")
        self._target_mb_entry.pack(side="left", fill="x", expand=True)
        self._target_mb_entry.bind("<FocusOut>", lambda _: self._on_setting_change())

        # Checkboxlar
        self._sharpen_var = BooleanVar(value=True)
        ctk.CTkCheckBox(
            p, text="Sharpen  (Steam için önerilir)",
            variable=self._sharpen_var,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT,
            fg_color=C_ACCENT, hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
            command=self._on_setting_change
        ).pack(anchor="w", padx=14, pady=4)

        self._smooth_var = BooleanVar(value=False)
        ctk.CTkCheckBox(
            p, text="Motion Smooth  (minterpolate)",
            variable=self._smooth_var,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=C_TEXT,
            fg_color=C_ACCENT, hover_color=C_ACC_LT,
            checkmark_color=C_BG0,
            command=self._on_setting_change
        ).pack(anchor="w", padx=14, pady=4)

        self._sep(p)

        # Tahmini boyut kartı
        est_card = ctk.CTkFrame(p, fg_color=C_BG3, corner_radius=10)
        est_card.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(est_card, text="TAHMİNİ BOYUT",
                     font=ctk.CTkFont("Segoe UI", 8, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=12, pady=(8, 2))
        self._est_lbl = ctk.CTkLabel(
            est_card, text="—",
            font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
            text_color=C_ACCENT)
        self._est_lbl.pack(pady=(0, 10))
        self._apply_profile(self._profile_var.get(), trigger=False)
        self._sync_effect_gallery()

    def _apply_profile(self, name, trigger=True):
        profile = QUALITY_PROFILES.get(name)
        if not profile:
            return
        self._fmt_var.set(profile["fmt"])
        self._res_var.set(profile["width"])
        self._fps_row.set(profile["fps"])
        self._lossy_row.set(profile["lossy"])
        self._color_var.set(profile["colors"])
        self._sharpen_var.set(profile["sharpen"])
        self._smooth_var.set(profile["smooth"])
        if trigger:
            self._on_setting_change()

    def _select_effect(self, name):
        self._effect_var.set(name)
        self._sync_effect_gallery()
        self._on_setting_change()

    def _on_effect_menu_change(self, *_):
        self._sync_effect_gallery()
        self._on_setting_change()

    def _toggle_effect_gallery(self):
        self._effect_gallery_open = not self._effect_gallery_open
        self._sync_effect_gallery_visibility()

    def _sync_effect_gallery_visibility(self):
        toggle = self._effect_gallery_toggle
        body = self._effect_gallery_body
        if not toggle or not body:
            return
        parent = body.master
        for child in parent.winfo_children():
            if child not in (toggle, body):
                try:
                    child.pack_forget()
                except Exception:
                    pass
        selected = self._effect_var.get()
        arrow = "v" if self._effect_gallery_open else ">"
        toggle.configure(text=f"{arrow} Efekt galerisi   |   {selected}")
        if self._effect_gallery_open:
            body.pack(fill="x", padx=0, pady=(0, 8))
        else:
            body.pack_forget()

    def _sync_effect_gallery(self):
        selected = self._effect_var.get()
        self._sync_effect_gallery_visibility()
        for name, btn in self._effect_buttons.items():
            active = name == selected
            btn.configure(
                fg_color=C_ACCENT if active else C_BG4,
                hover_color=C_ACC_LT if active else C_BG5,
                text_color=C_BG0 if active else C_TEXT,
                border_color=C_ACCENT if active else C_BORDER)

    def _user_preset_names(self):
        names = sorted(self._user_presets.keys())
        return names if names else ["Preset yok"]

    def _first_user_preset_name(self):
        return self._user_preset_names()[0]

    def _refresh_user_presets(self, selected=None):
        names = self._user_preset_names()
        try:
            self._user_preset_menu.configure(values=names)
        except Exception:
            pass
        self._user_preset_var.set(selected if selected in names else names[0])

    def _current_preset_payload(self):
        return {
            "effect": self._effect_var.get(),
            "border": self._border_row.get(),
            "glow": self._glow_row.get(),
            "intensity": self._intensity_row.get(),
            "bloom": self._bloom_row.get(),
            "vignette": self._vignette_row.get(),
            "particles": self._particle_row.get(),
            "border_template": self._border_template_var.get(),
            "sharpen": self._sharpen_var.get(),
            "smooth": self._smooth_var.get(),
        }

    def _apply_preset_payload(self, payload):
        effect = payload.get("effect", self._effect_var.get())
        if effect in EFFECT_PRESETS:
            self._effect_var.set(effect)
        self._border_row.set(payload.get("border", self._border_row.get()))
        self._glow_row.set(payload.get("glow", self._glow_row.get()))
        self._intensity_row.set(payload.get("intensity", self._intensity_row.get()))
        self._bloom_row.set(payload.get("bloom", self._bloom_row.get()))
        self._vignette_row.set(payload.get("vignette", self._vignette_row.get()))
        self._particle_row.set(payload.get("particles", self._particle_row.get()))
        template = payload.get("border_template")
        if template in ([BORDER_TEMPLATE_NONE] + _list_border_templates()):
            self._border_template_var.set(template)
        self._sharpen_var.set(bool(payload.get("sharpen", self._sharpen_var.get())))
        self._smooth_var.set(bool(payload.get("smooth", self._smooth_var.get())))
        self._sync_effect_gallery()
        self._on_setting_change()

    def _save_user_preset(self):
        dialog = ctk.CTkInputDialog(
            text="Preset adı",
            title="Preset Kaydet")
        name = (dialog.get_input() or "").strip()
        if not name:
            return
        self._user_presets[name] = self._current_preset_payload()
        _save_effect_presets(self._user_presets)
        self._refresh_user_presets(name)
        self._status.ok(f"Preset kaydedildi: {name}")

    def _apply_user_preset(self):
        name = self._user_preset_var.get()
        payload = self._user_presets.get(name)
        if not payload:
            self._status.error("Preset seçilmedi")
            return
        self._apply_preset_payload(payload)
        self._status.ok(f"Preset yüklendi: {name}")

    # ── Kaynak yükleme ────────────────────────────────────
    def _pick_media(self):
        p = filedialog.askopenfilename(
            filetypes=[
                ("Video / Görsel", "*.mp4;*.mov;*.avi;*.mkv;*.webm;*.gif;*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("Video", "*.mp4;*.mov;*.avi;*.mkv;*.webm"),
                ("Görsel", "*.gif;*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
            ])
        if p:
            self._load_media(p)

    def _load_media(self, path):
        if _is_image_file(path):
            self._load_image(path)
        else:
            self._load_video(path)

    def _load_video(self, path):
        self.video_path = path
        self.source_kind = "video"
        self.video_width, self.video_height = get_video_resolution(path)
        self.video_duration = get_video_duration(path)

        temp_thumb = os.path.join(tempfile.gettempdir(), "gif_thumb.jpg")
        run([FFMPEG, "-y", "-ss", "1", "-i", path,
             "-frames:v", "1", temp_thumb])

        info = (f"{os.path.basename(path)}\n"
                f"{self.video_width}×{self.video_height}  "
                f"{self.video_duration:.1f}s")
        self._preview.show(temp_thumb, info)
        self._status.set(f"Yüklendi: {os.path.basename(path)}",
                         C_SUCCESS, C_SUCCESS)
        self._trigger_estimate()
        self._trigger_effect_preview()

    def _load_image(self, path):
        self.video_path = path
        self.source_kind = "image"
        img = Image.open(path)
        self.video_width, self.video_height = img.size
        frame_count = 1
        total_ms = img.info.get("duration", 1000)
        if path.lower().endswith(".gif"):
            durations = []
            for frame in ImageSequence.Iterator(img):
                frame_count += 1 if frame_count == 0 else 0
                durations.append(frame.info.get("duration", img.info.get("duration", 80)))
            frame_count = max(1, len(durations))
            total_ms = sum(durations) if durations else total_ms
        self.video_duration = max(0.2, total_ms / 1000.0)

        info = (f"{os.path.basename(path)}\n"
                f"{self.video_width}×{self.video_height}  "
                f"{frame_count} kare" if path.lower().endswith(".gif")
                else f"{os.path.basename(path)}\n{self.video_width}×{self.video_height}  görsel")
        self._preview.show(path, info)
        self._status.set(f"Görsel yüklendi: {os.path.basename(path)}",
                         C_SUCCESS, C_SUCCESS)
        self._trigger_estimate()
        self._trigger_effect_preview()

    # ── Ayar değişince ────────────────────────────────────
    def _on_setting_change(self, _=None):
        self._sync_effect_gallery()
        self._trigger_effect_preview()
        self._trigger_estimate()

    def _trigger_effect_preview(self):
        if not self.video_path:
            return
        if self._fx_after_id:
            try:
                self.after_cancel(self._fx_after_id)
            except Exception:
                pass
            self._fx_after_id = None

        self._fx_after_id = self.after(40, self._start_effect_preview)

    def _start_effect_preview(self):
        self._fx_after_id = None
        source = self._preview.get_source_image()
        if source is None:
            return

        sharpen= self._sharpen_var.get()
        effect = self._effect_code()
        params = self._effect_params()

        try:
            img = _apply_effect_to_image(source, sharpen, effect, **params)
            if self._show_before_var.get():
                img = _make_before_after_preview(source, img)
            # Tek tuval: efektli kare ana önizlemeye basılır (WYSIWYG);
            # boyutlandırmayı VideoPreview kendisi yapar.
            self._preview.show_effect_image(img)
        except Exception as e:
            self._status.error(f"Efekt önizlemesi başarısız: {e}")

    # ── Tahmin (arka plan thread) ─────────────────────────
    def _trigger_estimate(self):
        if not self.video_path:
            return
        if self._est_after_id:
            try:
                self.after_cancel(self._est_after_id)
            except Exception:
                pass
            self._est_after_id = None

        self._est_cancel.set()

        if self._fmt_var.get() != "GIF":
            self._est_lbl.configure(text="—", text_color=C_DIM)
            self._status.set_size("")
            return

        self._est_lbl.configure(text="...", text_color=C_DIM)
        self._est_after_id = self.after(1400, self._start_estimate)

    def _start_estimate(self):
        self._est_after_id = None

        cancel = threading.Event()
        self._est_cancel = cancel

        fps    = self._fps_row.get()
        out_w  = int(self._res_var.get())
        colors = int(self._color_var.get())
        lossy  = self._lossy_row.get()
        dur    = self._get_duration()
        sharpen= self._sharpen_var.get()
        smooth = self._smooth_var.get()
        effect = self._effect_code()
        params = self._effect_params()
        vpath  = self.video_path
        source_kind = self.source_kind

        def worker():
            if source_kind == "image":
                result = _estimate_image_size(
                    vpath, "GIF", out_w, dur, fps, lossy, colors, sharpen,
                    effect, **params)
            else:
                result = _estimate_size(
                    vpath, fps, out_w, colors, lossy, dur, sharpen, smooth,
                    effect, **params, cancel_event=cancel)
            if cancel.is_set():
                return
            self.after(0, lambda: self._show_estimate(result))

        threading.Thread(target=worker, daemon=True).start()

    def _show_estimate(self, bytes_val):
        self._last_est_bytes = bytes_val
        if not bytes_val:
            self._est_lbl.configure(text="?", text_color=C_DIM)
            self._status.set_size("")
            return
        mb = bytes_val / (1024 * 1024)
        color = C_SUCCESS if mb < 5 else (C_ACCENT if mb < 10 else C_ERROR)
        self._est_lbl.configure(text=f"{mb:.2f} MB", text_color=color)
        self._status.set_size(f"~{mb:.2f} MB")

    # ── Dönüştür ──────────────────────────────────────────
    def _convert(self):
        if not self.video_path:
            self._status.error("Önce video veya görsel seç")
            return

        fps    = self._fps_row.get()
        out_w  = int(self._res_var.get())
        dur    = self._get_duration()
        lossy  = self._lossy_row.get()
        colors = int(self._color_var.get())
        fmt    = self._fmt_var.get()
        sharpen= self._sharpen_var.get()
        smooth = self._smooth_var.get()
        effect = self._effect_code()
        params = self._effect_params()

        if fmt == "GIF":
            tuned = self._auto_fit_target()
            if tuned:
                fps    = self._fps_row.get()
                out_w  = int(self._res_var.get())
                lossy  = self._lossy_row.get()
                colors = int(self._color_var.get())
                self._status.set("Hedef MB için kalite ayarlandı", C_ACCENT, C_ACCENT)

        base, _ = os.path.splitext(self.video_path)
        out_path = base + ("_HD.webp" if fmt == "WebP" else "_HD.gif")

        self._status.busy("Dönüştürülüyor...")
        self._btn_convert.configure(state="disabled", text="⏳  Dönüştürülüyor...")

        def worker():
            if self.source_kind == "image":
                ok, msg = _convert_image(
                    self.video_path, out_path, fmt,
                    out_w, dur, fps, lossy, colors, sharpen, effect, **params)
            else:
                ok, msg = _convert_video(
                    self.video_path, out_path, fmt,
                    fps, out_w, dur, self.video_duration,
                    lossy, colors, sharpen, smooth, effect, **params)
            self.after(0, lambda: self._on_done(ok, msg, out_path))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, ok, msg, out_path):
        self._btn_convert.configure(state="normal", text="▶  Dönüştür")
        if ok:
            size_mb = os.path.getsize(out_path) / (1024*1024) if os.path.exists(out_path) else 0
            self._status.ok(f"Hazır! {os.path.basename(out_path)}  ({size_mb:.2f} MB)")
            self._open_folder(os.path.dirname(out_path))
            self._last_output_path = out_path
            self._btn_send_to_splitter.configure(state="normal", text_color=C_TEXT)
        else:
            self._status.error(msg)

    def _send_to_splitter(self):
        """Son dönüştürülen dosyayı doğrudan Steam Splitter'da (editor.py) açar."""
        if not self._last_output_path or not os.path.exists(self._last_output_path):
            self._status.error("Gönderilecek çıktı bulunamadı")
            return
        editor_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "editor.py")
        if not os.path.exists(editor_script):
            self._status.error("editor.py bulunamadı")
            return
        try:
            subprocess.Popen([sys.executable, editor_script, self._last_output_path],
                             cwd=os.path.dirname(editor_script),
                             creationflags=0)
            self._status.set(f"Steam Splitter açılıyor: {os.path.basename(self._last_output_path)}",
                             C_SUCCESS, C_SUCCESS)
        except Exception as e:
            self._status.error(f"Açılamadı: {e}")

    def _get_duration(self):
        txt = self._dur_entry.get().strip().replace(",", ".")
        if not txt:
            return self.video_duration
        try:
            d = float(txt)
            if self.source_kind == "image":
                return d if d > 0 else self.video_duration
            return min(d, self.video_duration) if d > 0 else self.video_duration
        except ValueError:
            return self.video_duration

    def _get_target_mb(self):
        txt = self._target_mb_entry.get().strip().replace(",", ".")
        if not txt:
            return None
        try:
            val = float(txt)
            return val if val > 0 else None
        except ValueError:
            return None

    def _auto_fit_target(self):
        target = self._get_target_mb()
        if not target or not self._last_est_bytes:
            return False
        current = self._last_est_bytes / (1024 * 1024)
        if current <= target:
            return False

        ratio = current / target
        changed = False
        if ratio > 1.15:
            self._lossy_row.set(min(200, self._lossy_row.get() + int(18 * min(ratio, 4))))
            changed = True
        if ratio > 1.35 and self._fps_row.get() > 12:
            self._fps_row.set(max(12, int(self._fps_row.get() / min(ratio, 1.8))))
            changed = True
        if ratio > 1.75:
            widths = ["1080", "720", "480"]
            cur = self._res_var.get()
            if cur in widths and widths.index(cur) < len(widths) - 1:
                self._res_var.set(widths[widths.index(cur) + 1])
                changed = True
        if ratio > 2.0:
            colors = ["256", "128", "64"]
            cur = self._color_var.get()
            if cur in colors and colors.index(cur) < len(colors) - 1:
                self._color_var.set(colors[colors.index(cur) + 1])
                changed = True
        return changed

    def _effect_code(self):
        return EFFECT_PRESETS.get(self._effect_var.get(), "none")

    def _effect_params(self):
        return {
            "border": self._border_row.get(),
            "glow": self._glow_row.get(),
            "intensity": self._intensity_row.get(),
            "bloom": self._bloom_row.get(),
            "vignette": self._vignette_row.get(),
            "particles": self._particle_row.get(),
            "border_template": self._border_template_var.get(),
        }

    def _open_folder(self, path):
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass


# ── Backend fonksiyonları ─────────────────────────────────

def run(cmd):
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True,
                             creationflags=_NO_WINDOW)
        out, err = p.communicate()
        if out: print(out)
        if err: print(err)
        return p.returncode == 0
    except FileNotFoundError:
        print(f"[hata] Araç bulunamadı: {cmd[0]}")
        return False
    except Exception as e:
        print(f"[hata] {e}")
        return False


def run_cancelable(cmd, cancel_event=None):
    """ffmpeg'i çalıştırır; iptal edilebilir.
    stdout/stderr ayrı bir thread ile sürekli boşaltılır; aksi halde
    ffmpeg'in bol stderr çıktısı PIPE tamponunu doldurup süreci kilitlerdi."""
    p = None
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             creationflags=_NO_WINDOW)
        out_chunks = []

        def _drain():
            try:
                for line in p.stdout:
                    out_chunks.append(line)
            except Exception:
                pass

        reader = threading.Thread(target=_drain, daemon=True)
        reader.start()

        while p.poll() is None:
            if cancel_event and cancel_event.is_set():
                p.terminate()
                try:
                    p.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=1.0)
                return False
            time.sleep(0.05)

        reader.join(timeout=1.0)
        if out_chunks:
            print("".join(out_chunks))
        return p.returncode == 0
    except FileNotFoundError:
        print(f"[hata] Araç bulunamadı: {cmd[0]}")
        return False
    except Exception as e:
        if p and p.poll() is None:
            try: p.kill()
            except Exception: pass
        print(f"[hata] {e}")
        return False


def _load_effect_presets():
    try:
        if os.path.exists(USER_PRESETS_FILE):
            with open(USER_PRESETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print("preset load error:", e)
    return {}


def _save_effect_presets(presets):
    try:
        with open(USER_PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("preset save error:", e)


def _is_image_file(path):
    return os.path.splitext(path)[1].lower() in {".gif", ".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _list_border_templates():
    if not os.path.isdir(BORDER_TEMPLATE_DIR):
        return []
    exts = {".png", ".webp", ".jpg", ".jpeg"}
    return sorted(
        name for name in os.listdir(BORDER_TEMPLATE_DIR)
        if os.path.splitext(name)[1].lower() in exts
        and os.path.isfile(os.path.join(BORDER_TEMPLATE_DIR, name))
    )


def get_video_resolution(path):
    try:
        cmd = [FFPROBE, "-v", "error",
               "-select_streams", "v:0",
               "-show_entries", "stream=width,height",
               "-of", "csv=s=x:p=0", path]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True,
                             creationflags=_NO_WINDOW)
        out, _ = p.communicate()
        out = out.strip()
        if "x" in out:
            w, h = out.split("x")
            return int(w), int(h)
    except FileNotFoundError:
        pass  # ffprobe yok, sessizce atla
    except Exception as e:
        print("resolution error:", e)
    return 720, 1280


def get_video_duration(path):
    try:
        cmd = [FFPROBE, "-v", "error",
               "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True,
                             creationflags=_NO_WINDOW)
        out, _ = p.communicate()
        return float(out.strip())
    except FileNotFoundError:
        pass  # ffprobe yok, sessizce atla
    except Exception as e:
        print("duration error:", e)
    return 3.0


def _apply_vignette(img, strength=0.45):
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    pad_x = max(1, int(w * 0.10))
    pad_y = max(1, int(h * 0.10))
    draw.ellipse((-pad_x, -pad_y, w + pad_x, h + pad_y), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(8, min(w, h) // 5)))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    alpha = ImageEnhance.Contrast(mask).enhance(1.8).point(
        lambda p: int((255 - p) * strength))
    return Image.composite(dark, img, alpha)


def _tint_image(img, color, amount):
    tint = Image.new("RGB", img.size, color)
    return Image.blend(img, tint, max(0.0, min(1.0, amount)))


def _bloom_image(img, amount=0.18, radius=8, brightness=1.35):
    bloom = ImageEnhance.Brightness(img).enhance(brightness)
    bloom = bloom.filter(ImageFilter.GaussianBlur(max(1, int(radius))))
    return Image.blend(img, bloom, max(0.0, min(1.0, amount)))


def _draw_scanlines(img, step=4, alpha=18, color=(255, 255, 255)):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, img.height, max(2, int(step))):
        draw.line((0, y, img.width, y), fill=color + (alpha,))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _draw_particles(img, color, amount=36, seed=1, vertical_bias=1.0):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = random.Random(seed)
    count = max(4, int(amount))
    for _ in range(count):
        x = rng.randint(0, max(1, img.width - 1))
        y = int((rng.random() ** vertical_bias) * max(1, img.height - 1))
        r = rng.randint(1, max(2, img.width // 180))
        a = rng.randint(55, 160)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color + (a,))
        if rng.random() < 0.28:
            draw.line((x, y, x + rng.randint(-12, 12), y + rng.randint(8, 28)),
                      fill=color + (a // 2,), width=1)
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.4))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _chromatic_shift(img, amount=3):
    amount = max(1, int(amount))
    r, g, b = img.split()
    r = ImageChops.offset(r, amount, 0) if "ImageChops" in globals() else r
    b = ImageChops.offset(b, -amount, 0) if "ImageChops" in globals() else b
    return Image.merge("RGB", (r, g, b))


def _make_before_after_preview(before, after):
    before = before.convert("RGB").resize(after.size, Image.LANCZOS)
    composed = after.copy()
    split_x = composed.width // 2
    composed.paste(before.crop((0, 0, split_x, composed.height)), (0, 0))
    draw = ImageDraw.Draw(composed)
    draw.line((split_x, 0, split_x, composed.height), fill=(249, 115, 22), width=3)
    return composed


def _effect_border_colors(effect):
    return {
        "neon": ((124, 58, 237), (34, 211, 238)),
        "dark_glow": ((168, 85, 247), (99, 102, 241)),
        "vhs": ((251, 146, 60), (255, 255, 255)),
        "cinema": ((12, 12, 12), (249, 115, 22)),
        "purple_soul": ((147, 51, 234), (216, 180, 254)),
        "blue_lightning": ((37, 99, 235), (125, 211, 252)),
        "blood_curse": ((153, 27, 27), (248, 113, 113)),
        "ice_mist": ((56, 189, 248), (224, 242, 254)),
        "golden_divine": ((245, 158, 11), (254, 240, 138)),
        "cyber_glitch": ((34, 211, 238), (236, 72, 153)),
        "vhs_horror": ((127, 29, 29), (255, 255, 255)),
        "inferno_ember": ((234, 88, 12), (253, 186, 116)),
    }.get(effect, ((46, 46, 46), (46, 46, 46)))


def _border_orb_position(w, h, inset, phase):
    left, top = inset, inset
    right, bottom = max(left, w - 1 - inset), max(top, h - 1 - inset)
    edge_w = max(1, right - left)
    edge_h = max(1, bottom - top)
    dist = (phase % 1.0) * (edge_w * 2 + edge_h * 2)
    if dist < edge_w:
        return left + dist, top
    dist -= edge_w
    if dist < edge_h:
        return right, top + dist
    dist -= edge_h
    if dist < edge_w:
        return right - dist, bottom
    dist -= edge_w
    return left, bottom - dist


def _draw_glow_border(img, border, border_color, inner_color, glow_strength=0.45,
                      orb_phase=None):
    border = max(0, int(border or 0))
    if border <= 0:
        return img

    glow_strength = max(0.0, min(1.0, float(glow_strength or 0.0)))
    line_w = max(1, border)
    inset = max(1, line_w // 2)
    box = (inset, inset, img.width - 1 - inset, img.height - 1 - inset)

    base = img.convert("RGBA")
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    for spread, alpha in (
        (line_w * 4, int(46 + glow_strength * 70)),
        (line_w * 2, int(64 + glow_strength * 85)),
    ):
        glow_draw.rectangle(
            (box[0], box[1], box[2], box[3]),
            outline=border_color + (alpha,),
            width=max(2, line_w + spread // 6),
        )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(max(2, int(line_w * (1.6 + glow_strength)))))
    base = Image.alpha_composite(base, glow_layer)

    line_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    line_draw = ImageDraw.Draw(line_layer)
    line_draw.rectangle(box, outline=border_color + (210,), width=line_w)
    if img.width > line_w * 5 and img.height > line_w * 5:
        inner = (
            min(box[0] + line_w * 2, img.width - 1),
            min(box[1] + line_w * 2, img.height - 1),
            max(box[2] - line_w * 2, 0),
            max(box[3] - line_w * 2, 0),
        )
        if inner[2] > inner[0] and inner[3] > inner[1]:
            line_draw.rectangle(inner, outline=inner_color + (120,), width=max(1, line_w // 2))
    base = Image.alpha_composite(base, line_layer)

    if orb_phase is not None and img.width > line_w * 8 and img.height > line_w * 8:
        x, y = _border_orb_position(img.width, img.height, inset, orb_phase)
        radius = max(4, line_w * 2)
        orb = Image.new("RGBA", img.size, (0, 0, 0, 0))
        orb_draw = ImageDraw.Draw(orb)
        orb_draw.ellipse(
            (x - radius * 3, y - radius * 3, x + radius * 3, y + radius * 3),
            fill=inner_color + (95,),
        )
        orb = orb.filter(ImageFilter.GaussianBlur(max(3, radius)))
        core_draw = ImageDraw.Draw(orb)
        core_draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=inner_color + (235,),
            outline=(255, 255, 255, 210),
            width=max(1, radius // 3),
        )
        core_draw.ellipse(
            (x - radius // 2, y - radius // 2, x + radius // 2, y + radius // 2),
            fill=(255, 255, 255, 190),
        )
        base = Image.alpha_composite(base, orb)

    return base.convert("RGB")


def _template_alpha_mask(template):
    alpha = template.getchannel("A")
    if alpha.getextrema() != (255, 255):
        return alpha
    # Alfa kanalı yoksa (tamamen opak PNG): açık renkleri şeffaf say, koyu
    # kenarlık çizgilerini görünür bırak.
    gray = template.convert("L")
    return gray.point(lambda p: 0 if p > 245 else 255)


def _apply_border_template(img, template_name, color, glow_strength=0.45, opacity=1.0):
    if not template_name or template_name == BORDER_TEMPLATE_NONE:
        return img
    path = os.path.join(BORDER_TEMPLATE_DIR, template_name)
    if not os.path.isfile(path):
        return img
    try:
        base = img.convert("RGBA")
        template = Image.open(path).convert("RGBA").resize(base.size, Image.LANCZOS)
        mask = _template_alpha_mask(template)
        opacity = max(0.0, min(1.0, float(opacity or 1.0)))
        glow_strength = max(0.0, min(1.0, float(glow_strength or 0.0)))
        mask = mask.point(lambda p: int(p * opacity))

        if glow_strength > 0:
            glow_alpha = mask.filter(ImageFilter.GaussianBlur(max(2, int(24 * glow_strength))))
            glow_alpha = glow_alpha.point(lambda p: int(p * min(1.0, 0.30 + glow_strength * 0.70)))
            glow_layer = Image.new("RGBA", base.size, color + (0,))
            glow_layer.putalpha(glow_alpha)
            base = Image.alpha_composite(base, glow_layer)

        template.putalpha(mask)
        return Image.alpha_composite(base, template).convert("RGB")
    except Exception as e:
        print(f"border template error: {path} | {e}")
        return img


def _apply_border_template_to_output(out_path, fmt, template_name, effect, glow,
                                     colors=128, lossy=20, eff_dur=1.0, fps=12):
    """Video kaynağından ffmpeg ile üretilen GIF/WebP çıktısına border template'i
    PIL ile sonradan bindirir. ffmpeg filtre zinciri PNG border template overlay'i
    uygulayamadığı için, video dönüştürmede Template ayarı bu adım olmadan
    sessizce yok sayılırdı (görsel/GIF kaynaklar zaten PIL üzerinden geçiyor)."""
    if not template_name or template_name == BORDER_TEMPLATE_NONE:
        return
    if not os.path.isfile(out_path):
        return
    try:
        _, inner_color = _effect_border_colors(effect)
        glow_strength = max(0, min(100, int(glow or 0))) / 100.0
        with Image.open(out_path) as im:
            frames = []
            durations = []
            for frame in ImageSequence.Iterator(im):
                frames.append(frame.convert("RGB").copy())
                durations.append(frame.info.get("duration", 40))
        frames = [_apply_border_template(f, template_name, inner_color, glow_strength, 1.0)
                  for f in frames]
        if fmt == "WebP":
            frames[0].save(out_path, "WEBP", save_all=True, append_images=frames[1:],
                           duration=durations, loop=0, quality=80, method=6)
        else:
            _save_effect_frames_as_gif(frames, out_path, eff_dur, fps, lossy, colors)
    except Exception as e:
        print(f"border template postprocess error: {out_path} | {e}")


def _apply_effect_to_image(img, sharpen, effect="none", border=0, glow=0,
                           intensity=75, bloom=55, vignette=45, particles=45,
                           border_template=BORDER_TEMPLATE_NONE):
    img = img.convert("RGB")
    border = max(0, int(border or 0))
    glow = max(0, min(100, int(glow or 0))) / 100.0
    intensity = max(0, min(100, int(intensity or 0))) / 100.0
    bloom = max(0, min(100, int(bloom or 0))) / 100.0
    vignette = max(0, min(100, int(vignette or 0))) / 100.0
    particles = max(0, min(100, int(particles or 0))) / 100.0
    fx = 0.35 + intensity * 0.95
    glow_fx = glow * fx
    bloom_fx = bloom * fx
    vignette_fx = vignette * fx
    particle_fx = particles * fx

    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=135, threshold=3))

    if effect == "neon":
        img = ImageEnhance.Contrast(img).enhance(1.08)
        img = ImageEnhance.Color(img).enhance(1.10 + glow_fx * 0.55)
        glow_layer = ImageEnhance.Brightness(img).enhance(1.18 + glow_fx * 0.30)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(max(2, int(7 * glow_fx))))
        img = Image.blend(img, glow_layer, 0.12 + bloom_fx * 0.18)
        img = _apply_vignette(img, 0.12 + vignette_fx * 0.28)
        border_color = (124, 58, 237)
        inner_color = (34, 211, 238)
    elif effect == "dark_glow":
        img = ImageEnhance.Brightness(img).enhance(0.78)
        img = ImageEnhance.Contrast(img).enhance(1.18)
        img = ImageEnhance.Color(img).enhance(1.02 + glow_fx * 0.28)
        blue = Image.new("RGB", img.size, (18, 24, 62))
        img = Image.blend(img, blue, 0.08 + intensity * 0.16)
        halo = ImageEnhance.Brightness(img).enhance(1.35 + glow_fx * 0.45)
        halo = halo.filter(ImageFilter.GaussianBlur(max(3, int(10 * glow_fx))))
        img = Image.blend(img, halo, 0.08 + bloom_fx * 0.18)
        img = _apply_vignette(img, 0.30 + vignette_fx * 0.48)
        border_color = (168, 85, 247)
        inner_color = (99, 102, 241)
    elif effect == "vhs":
        img = ImageEnhance.Contrast(img).enhance(1.06)
        img = ImageEnhance.Color(img).enhance(0.88)
        img = _draw_scanlines(img, 4, int(10 + particle_fx * 28), (255, 255, 255))
        border_color = (251, 146, 60)
        inner_color = (255, 255, 255)
    elif effect == "cinema":
        img = ImageEnhance.Brightness(img).enhance(0.96 - intensity * 0.08)
        img = ImageEnhance.Contrast(img).enhance(1.04 + intensity * 0.16)
        img = ImageEnhance.Color(img).enhance(0.92 + glow_fx * 0.14)
        img = _apply_vignette(img, 0.20 + vignette_fx * 0.48)
        border_color = (12, 12, 12)
        inner_color = (249, 115, 22)
    elif effect == "purple_soul":
        img = ImageEnhance.Brightness(img).enhance(0.86)
        img = ImageEnhance.Contrast(img).enhance(1.22)
        img = ImageEnhance.Color(img).enhance(1.20 + glow_fx * 0.42)
        img = _tint_image(img, (70, 28, 135), 0.10 + intensity * 0.16)
        img = _bloom_image(img, 0.12 + bloom_fx * 0.30, 8 + bloom_fx * 18, 1.55)
        img = _draw_particles(img, (168, 85, 247), 8 + particle_fx * 62, 101, 0.75)
        img = _apply_vignette(img, 0.20 + vignette_fx * 0.45)
        border_color = (147, 51, 234)
        inner_color = (216, 180, 254)
    elif effect == "blue_lightning":
        img = ImageEnhance.Contrast(img).enhance(1.28)
        img = ImageEnhance.Color(img).enhance(1.12)
        img = _tint_image(img, (16, 72, 180), 0.10 + intensity * 0.14)
        img = _bloom_image(img, 0.10 + bloom_fx * 0.32, 5 + bloom_fx * 16, 1.65)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        rng = random.Random(202)
        for _ in range(5):
            x = rng.randint(img.width // 8, img.width * 7 // 8)
            y = rng.randint(0, img.height // 2)
            pts = [(x, y)]
            for _ in range(6):
                x += rng.randint(-28, 28)
                y += rng.randint(24, 58)
                pts.append((x, y))
            draw.line(pts, fill=(96, 165, 250, int(70 + particle_fx * 145)), width=2)
            draw.line(pts, fill=(219, 234, 254, int(45 + particle_fx * 95)), width=1)
        img = Image.alpha_composite(img.convert("RGBA"), overlay.filter(ImageFilter.GaussianBlur(0.3))).convert("RGB")
        img = _apply_vignette(img, 0.34)
        border_color = (37, 99, 235)
        inner_color = (125, 211, 252)
    elif effect == "blood_curse":
        img = ImageEnhance.Brightness(img).enhance(0.72)
        img = ImageEnhance.Contrast(img).enhance(1.32)
        img = ImageEnhance.Color(img).enhance(0.85)
        img = _tint_image(img, (105, 10, 25), 0.14 + intensity * 0.24)
        img = _bloom_image(img, 0.06 + bloom_fx * 0.18, 7 + bloom_fx * 12, 1.25)
        img = _draw_particles(img, (220, 38, 38), 8 + particle_fx * 38, 303, 0.55)
        img = _apply_vignette(img, 0.34 + vignette_fx * 0.44)
        border_color = (153, 27, 27)
        inner_color = (248, 113, 113)
    elif effect == "ice_mist":
        img = ImageEnhance.Brightness(img).enhance(1.03)
        img = ImageEnhance.Contrast(img).enhance(0.96)
        img = ImageEnhance.Color(img).enhance(0.78)
        img = _tint_image(img, (186, 230, 253), 0.14 + intensity * 0.22)
        mist = Image.new("RGBA", img.size, (210, 245, 255, int(12 + bloom_fx * 72)))
        mist = mist.filter(ImageFilter.GaussianBlur(max(6, img.width // 70)))
        img = Image.alpha_composite(img.convert("RGBA"), mist).convert("RGB")
        img = _draw_particles(img, (224, 242, 254), 12 + particle_fx * 62, 404, 1.10)
        img = _apply_vignette(img, 0.10 + vignette_fx * 0.28)
        border_color = (56, 189, 248)
        inner_color = (224, 242, 254)
    elif effect == "golden_divine":
        img = ImageEnhance.Brightness(img).enhance(1.08)
        img = ImageEnhance.Contrast(img).enhance(1.16)
        img = ImageEnhance.Color(img).enhance(1.18)
        img = _tint_image(img, (245, 158, 11), 0.08 + intensity * 0.16)
        img = _bloom_image(img, 0.14 + bloom_fx * 0.34, 10 + bloom_fx * 22, 1.70)
        img = _draw_particles(img, (253, 224, 71), 10 + particle_fx * 78, 505, 0.80)
        img = _apply_vignette(img, 0.10 + vignette_fx * 0.34)
        border_color = (245, 158, 11)
        inner_color = (254, 240, 138)
    elif effect == "cyber_glitch":
        img = ImageEnhance.Contrast(img).enhance(1.20)
        img = ImageEnhance.Color(img).enhance(1.30)
        img = _chromatic_shift(img, 1 + intensity * 7)
        img = _draw_scanlines(img, 3, int(12 + particle_fx * 50), (34, 211, 238))
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        rng = random.Random(606)
        for _ in range(10):
            y = rng.randint(0, img.height - 1)
            h = rng.randint(2, max(3, img.height // 70))
            draw.rectangle((0, y, img.width, y + h), fill=(236, 72, 153, rng.randint(28, 80)))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        border_color = (34, 211, 238)
        inner_color = (236, 72, 153)
    elif effect == "vhs_horror":
        img = ImageEnhance.Brightness(img).enhance(0.68)
        img = ImageEnhance.Contrast(img).enhance(1.30)
        img = ImageEnhance.Color(img).enhance(0.55)
        img = _tint_image(img, (85, 20, 20), 0.08 + intensity * 0.18)
        img = _draw_scanlines(img, 4, 18 + int(particle_fx * 42), (255, 255, 255))
        img = _draw_particles(img, (160, 160, 160), 8 + particle_fx * 34, 707, 1.0)
        img = _apply_vignette(img, 0.36 + vignette_fx * 0.48)
        border_color = (127, 29, 29)
        inner_color = (255, 255, 255)
    elif effect == "inferno_ember":
        img = ImageEnhance.Brightness(img).enhance(0.86)
        img = ImageEnhance.Contrast(img).enhance(1.24)
        img = ImageEnhance.Color(img).enhance(1.28)
        img = _tint_image(img, (194, 65, 12), 0.10 + intensity * 0.22)
        img = _bloom_image(img, 0.12 + bloom_fx * 0.30, 8 + bloom_fx * 20, 1.55)
        img = _draw_particles(img, (251, 146, 60), 12 + particle_fx * 94, 808, 0.42)
        img = _apply_vignette(img, 0.18 + vignette_fx * 0.42)
        border_color = (234, 88, 12)
        inner_color = (253, 186, 116)
    else:
        border_color = (46, 46, 46)
        inner_color = (46, 46, 46)

    if border:
        img = _draw_glow_border(img, border, border_color, inner_color, glow)
    img = _apply_border_template(img, border_template, inner_color, glow / 100.0, 1.0)
    return img


def _extra_filters(sharpen, smooth, effect="none", border=0, glow=0,
                   intensity=75, bloom=55, vignette=45, particles=45):
    f = []
    if smooth:  f.append("minterpolate='mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1'")
    if sharpen: f.append("unsharp=3:3:0.7")

    border = max(0, int(border or 0))
    glow = max(0, min(100, int(glow or 0))) / 100.0
    intensity = max(0, min(100, int(intensity or 0))) / 100.0
    bloom = max(0, min(100, int(bloom or 0))) / 100.0
    vignette = max(0, min(100, int(vignette or 0))) / 100.0
    particles = max(0, min(100, int(particles or 0))) / 100.0
    fx = 0.35 + intensity * 0.95
    glow_fx = glow * fx
    bloom_fx = bloom * fx
    vignette_fx = vignette * fx
    particle_fx = particles * fx
    glow_gain = 1.0 + (0.35 * glow_fx)
    sat_gain = 1.0 + (0.35 * intensity)
    noise = max(1, int(2 + particle_fx * 14))
    scan_alpha = 0.03 + particle_fx * 0.12
    vignette_angle = max(3.0, 9.0 - vignette_fx * 5.0)

    if effect == "neon":
        f.append(f"eq=contrast=1.08:brightness=0.01:saturation={sat_gain:.2f}:gamma={glow_gain:.2f}")
        f.append("hue=h=6*sin(2*PI*t/4):s=1.04")
        f.append(f"vignette=PI/{vignette_angle:.2f}")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#7c3aed@0.95:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#22d3ee@0.45:t=2")
    elif effect == "dark_glow":
        f.append(f"eq=contrast=1.12:brightness=-0.025:saturation={sat_gain:.2f}:gamma={glow_gain:.2f}")
        f.append("colorbalance=rs=-0.05:gs=-0.02:bs=0.08")
        f.append(f"vignette=PI/{max(3.0, vignette_angle - 0.8):.2f}")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#a855f7@0.85:t={border}")
    elif effect == "vhs":
        f.append("format=yuv420p")
        f.append(f"noise=alls={noise}:allf=t+u")
        f.append(f"drawgrid=w=iw:h=4:t=1:c=white@{scan_alpha:.2f}")
        f.append("eq=contrast=1.06:saturation=0.92")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#fb923c@0.60:t={border}")
    elif effect == "cinema":
        f.append(f"eq=contrast=1.10:brightness=-0.015:saturation={max(0.85, sat_gain - 0.10):.2f}")
        f.append(f"vignette=PI/{vignette_angle:.2f}")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.55:t={border}")
    elif effect == "purple_soul":
        f.append(f"eq=contrast=1.22:brightness=-0.035:saturation={1.15 + glow * 0.45:.2f}:gamma={1.04 + glow * 0.16:.2f}")
        f.append("colorbalance=rs=0.04:gs=-0.06:bs=0.16")
        f.append("hue=h=8*sin(2*PI*t/3):s=1.08")
        f.append("vignette=PI/4")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#9333ea@0.95:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#d8b4fe@0.52:t=2")
    elif effect == "blue_lightning":
        f.append(f"eq=contrast=1.28:brightness=0.005:saturation={1.05 + glow * 0.30:.2f}:gamma={1.02 + glow * 0.12:.2f}")
        f.append("colorbalance=rs=-0.10:gs=0.02:bs=0.24")
        f.append("hue=h=5*sin(2*PI*t*2):s=1.05")
        f.append("drawgrid=w=iw:h=48:t=1:c=#60a5fa@0.08")
        f.append("vignette=PI/5")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#2563eb@0.92:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#7dd3fc@0.55:t=2")
    elif effect == "blood_curse":
        f.append("eq=contrast=1.32:brightness=-0.075:saturation=0.88:gamma=0.98")
        f.append("colorbalance=rs=0.22:gs=-0.10:bs=-0.10")
        f.append("noise=alls=4:allf=t+u")
        f.append("vignette=PI/3")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#991b1b@0.95:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#f87171@0.45:t=2")
    elif effect == "ice_mist":
        f.append(f"eq=contrast=0.96:brightness=0.035:saturation={0.72 + glow * 0.12:.2f}:gamma=1.04")
        f.append("colorbalance=rs=-0.12:gs=0.04:bs=0.20")
        f.append("noise=alls=3:allf=t+u")
        f.append("vignette=PI/7")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#38bdf8@0.75:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#e0f2fe@0.42:t=2")
    elif effect == "golden_divine":
        f.append(f"eq=contrast=1.16:brightness=0.035:saturation={1.15 + glow * 0.25:.2f}:gamma={1.06 + glow * 0.12:.2f}")
        f.append("colorbalance=rs=0.18:gs=0.08:bs=-0.12")
        f.append("hue=h=3*sin(2*PI*t/4):s=1.05")
        f.append("vignette=PI/6")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#f59e0b@0.88:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#fef08a@0.52:t=2")
    elif effect == "cyber_glitch":
        f.append(f"eq=contrast=1.20:brightness=0.005:saturation={1.22 + glow * 0.32:.2f}")
        f.append("rgbashift=rh=3:bh=-3")
        f.append("noise=alls=7:allf=t+u")
        f.append("drawgrid=w=iw:h=3:t=1:c=#22d3ee@0.10")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#22d3ee@0.90:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#ec4899@0.55:t=2")
    elif effect == "vhs_horror":
        f.append("eq=contrast=1.30:brightness=-0.095:saturation=0.58:gamma=0.96")
        f.append("colorbalance=rs=0.14:gs=-0.08:bs=-0.08")
        f.append("noise=alls=12:allf=t+u")
        f.append("drawgrid=w=iw:h=4:t=1:c=white@0.08")
        f.append("vignette=PI/3")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#7f1d1d@0.90:t={border}")
    elif effect == "inferno_ember":
        f.append(f"eq=contrast=1.24:brightness=-0.035:saturation={1.20 + glow * 0.35:.2f}:gamma={1.02 + glow * 0.10:.2f}")
        f.append("colorbalance=rs=0.22:gs=0.02:bs=-0.15")
        f.append("noise=alls=5:allf=t+u")
        f.append("vignette=PI/4")
        if border:
            f.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=#ea580c@0.92:t={border}")
            f.append(f"drawbox=x={border * 2}:y={border * 2}:w=iw-{border * 4}:h=ih-{border * 4}:color=#fdba74@0.50:t=2")
    return ",".join(f)


def _video_filters(fps, out_w, sharpen, smooth, effect, border, glow,
                   intensity=75, bloom=55, vignette=45, particles=45):
    filters = [f"fps={fps}", f"scale={out_w}:-1:flags=lanczos", "setsar=1"]
    extra = _extra_filters(sharpen, smooth, effect, border, glow,
                           intensity, bloom, vignette, particles)
    if extra:
        filters.append(extra)
    return ",".join(filters)


def _paletteuse_filter(lossy):
    lossy = max(0, int(lossy or 0))
    if lossy >= 80:
        return "paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    if lossy >= 45:
        return "paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle"
    return "paletteuse=dither=sierra2_4a:diff_mode=rectangle"


def _prepare_effect_base(path, out_w):
    img = Image.open(path).convert("RGB")
    out_w = max(1, int(out_w or img.width))
    if img.width != out_w:
        out_h = max(1, int(img.height * (out_w / img.width)))
        img = img.resize((out_w, out_h), Image.LANCZOS)
    return img


def _resize_effect_frame(img, out_w):
    img = img.convert("RGB")
    out_w = max(1, int(out_w or img.width))
    if img.width == out_w:
        return img
    out_h = max(1, int(img.height * (out_w / img.width)))
    return img.resize((out_w, out_h), Image.LANCZOS)


def _prepare_effect_image(path, out_w, sharpen, effect="none", **params):
    img = _prepare_effect_base(path, out_w)
    return _apply_effect_to_image(img, sharpen, effect, **params)


def _animation_frame_count(duration, fps, effect):
    if effect == "none":
        return 1
    duration = max(0.2, float(duration or 1.0))
    fps = max(5, min(24, int(fps or 12)))
    return max(2, min(96, int(duration * fps)))


def _animated_effect_frame(base, frame_idx, frame_count, fps, sharpen, effect="none", **params):
    phase = frame_idx / max(1, frame_count)
    wave = math.sin(phase * math.tau)
    glow = int(params.get("glow", 0) or 0)
    intensity = int(params.get("intensity", 75) or 75)
    particles = int(params.get("particles", 45) or 45)
    border = int(params.get("border", 0) or 0)
    anim_params = dict(params)
    anim_params["glow"] = max(0, min(100, glow + int(10 * wave)))
    anim_params["intensity"] = max(0, min(100, intensity + int(6 * math.sin(phase * math.tau * 1.7))))
    anim_params["border"] = 0

    img = _apply_effect_to_image(base, sharpen, effect, **anim_params)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = random.Random(7300 + frame_idx * 97)

    if effect in {"vhs", "vhs_horror", "cyber_glitch", "blood_curse", "blue_lightning", "inferno_ember"}:
        offset = int((frame_idx * 2) % 6)
        alpha = 18 + min(45, particles // 2)
        for y in range(offset, img.height, 4):
            draw.line((0, y, img.width, y), fill=(255, 255, 255, alpha))

    if effect in {"cyber_glitch", "vhs", "vhs_horror"}:
        for _ in range(4 + particles // 18):
            y = rng.randint(0, max(0, img.height - 2))
            h = rng.randint(2, max(3, img.height // 45))
            x_shift = rng.randint(-18, 18)
            band = img.crop((0, y, img.width, min(img.height, y + h))).convert("RGBA")
            band.putalpha(rng.randint(40, 105))
            overlay.alpha_composite(band, (x_shift, y))
        img = _chromatic_shift(img, 1 + abs(int(wave * (2 + intensity // 18))))

    if effect in {"neon", "purple_soul", "blue_lightning", "golden_divine", "ice_mist", "inferno_ember", "blood_curse"}:
        colors = {
            "neon": (168, 85, 247),
            "purple_soul": (168, 85, 247),
            "blue_lightning": (96, 165, 250),
            "golden_divine": (253, 224, 71),
            "ice_mist": (224, 242, 254),
            "inferno_ember": (249, 115, 22),
            "blood_curse": (220, 38, 38),
        }
        color = colors.get(effect, (255, 255, 255))
        for _ in range(max(3, particles // 9)):
            x = rng.randint(0, max(1, img.width - 1))
            y = (rng.randint(0, max(1, img.height - 1)) + int(phase * img.height * 0.22)) % img.height
            r = rng.randint(1, max(2, img.width // 170))
            a = rng.randint(45, 135)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color + (a,))
            if rng.random() < 0.35:
                draw.line((x, y, x + rng.randint(-16, 16), y + rng.randint(10, 34)),
                          fill=color + (a // 2,), width=1)

    if effect == "blue_lightning":
        for _ in range(2):
            x = rng.randint(img.width // 8, img.width * 7 // 8)
            y = rng.randint(0, max(1, img.height // 3))
            pts = [(x, y)]
            for _ in range(5):
                x += rng.randint(-22, 22)
                y += rng.randint(18, 46)
                pts.append((x, y))
            draw.line(pts, fill=(125, 211, 252, 120), width=2)

    img = Image.alpha_composite(img.convert("RGBA"), overlay.filter(ImageFilter.GaussianBlur(0.2))).convert("RGB")
    if effect in {"neon", "purple_soul", "golden_divine", "inferno_ember"}:
        img = ImageEnhance.Brightness(img).enhance(1.0 + 0.04 * wave)
    if border > 0:
        border_color, inner_color = _effect_border_colors(effect)
        img = _draw_glow_border(
            img,
            border,
            border_color,
            inner_color,
            max(0.25, glow / 100.0),
            orb_phase=(phase + 0.12 * math.sin(phase * math.tau)) % 1.0,
        )
    return img


def _make_effect_frames(path, out_w, duration, fps, sharpen, effect="none", **params):
    if path.lower().endswith(".gif"):
        with Image.open(path) as gif:
            source_frames = [_resize_effect_frame(frame.copy(), out_w) for frame in ImageSequence.Iterator(gif)]
        if not source_frames:
            source_frames = [_prepare_effect_base(path, out_w)]
        max_frames = 96
        if len(source_frames) > max_frames:
            step = len(source_frames) / max_frames
            source_frames = [source_frames[int(i * step)] for i in range(max_frames)]
        frame_count = len(source_frames)
        return [
            _animated_effect_frame(source_frames[idx], idx, frame_count, fps, sharpen, effect, **params)
            for idx in range(frame_count)
        ]

    base = _prepare_effect_base(path, out_w)
    frame_count = _animation_frame_count(duration, fps, effect)
    return [
        _animated_effect_frame(base, idx, frame_count, fps, sharpen, effect, **params)
        for idx in range(frame_count)
    ]


def _save_effect_frames_as_gif(frames, out_path, duration, fps, lossy, colors):
    colors = max(2, min(256, int(colors or 128)))
    fps = max(5, min(24, int(fps or 12)))
    frame_ms = max(20, int(1000 / fps))
    if len(frames) == 1:
        frame_ms = max(20, int(float(duration or 1.0) * 1000))
    pal_frames = [f.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=colors) for f in frames]
    pal_frames[0].save(
        out_path,
        save_all=True,
        append_images=pal_frames[1:],
        duration=frame_ms,
        loop=0,
        disposal=2,
        optimize=True,
    )
    if not GIFSICLE_MISSING:
        tmp = out_path + ".opt.gif"
        if run([GIFSICLE, f"--lossy={int(lossy or 0)}",
                f"--colors={colors}", "-O3", out_path, "-o", tmp]):
            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                os.replace(tmp, out_path)
            elif os.path.exists(tmp):
                os.remove(tmp)


def _estimate_image_size(path, fmt, out_w, duration, fps, lossy, colors, sharpen,
                         effect="none", **params):
    td = tempfile.gettempdir()
    ext = ".webp" if fmt == "WebP" else ".gif"
    out = os.path.join(td, f"_img_est_{os.getpid()}{ext}")
    try:
        if fmt == "WebP":
            img = _prepare_effect_image(path, out_w, sharpen, effect, **params)
            img.save(out, "WEBP", quality=80, method=6)
        else:
            frames = _make_effect_frames(path, out_w, duration, fps, sharpen, effect, **params)
            _save_effect_frames_as_gif(frames, out, duration, fps, lossy, colors)
        return os.path.getsize(out) if os.path.exists(out) else None
    except Exception as e:
        print("image estimate error:", e)
        return None
    finally:
        try:
            if os.path.exists(out):
                os.remove(out)
        except Exception:
            pass


def _convert_image(path, out_path, fmt, out_w, duration, fps, lossy, colors, sharpen,
                   effect="none", **params):
    try:
        if fmt == "WebP":
            img = _prepare_effect_image(path, out_w, sharpen, effect, **params)
            img.save(out_path, "WEBP", quality=80, method=6)
            return True, "WebP hazır"
        frames = _make_effect_frames(path, out_w, duration, fps, sharpen, effect, **params)
        _save_effect_frames_as_gif(frames, out_path, duration, fps, lossy, colors)
        return True, f"Animasyonlu görsel GIF hazır ({len(frames)} kare)"
    except Exception as e:
        return False, str(e)


def _estimate_size(vpath, fps, out_w, colors, lossy, eff_dur, sharpen, smooth,
                   effect="none", border=0, glow=0,
                   intensity=75, bloom=55, vignette=45, particles=45,
                   border_template=BORDER_TEMPLATE_NONE,
                   cancel_event=None):
    chunk = min(0.6, eff_dur)
    td    = tempfile.gettempdir()
    # Her çağrıya özgü benzersiz ad: aynı süreçte iptal edilen bir tahmin ile
    # hemen ardından başlayan yenisi aynı dosyaya çakışmasın (yarış durumu).
    token = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    pal   = os.path.join(td, f"_est_pal_{token}.png")
    raw   = os.path.join(td, f"_est_raw_{token}.gif")
    opt   = os.path.join(td, f"_est_opt_{token}.gif")
    base_vf = _video_filters(fps, out_w, sharpen, smooth, effect, border, glow,
                             intensity, bloom, vignette, particles)
    try:
        vf_pal = f"{base_vf},palettegen=max_colors={colors}:stats_mode=diff"
        if cancel_event and cancel_event.is_set():
            return None
        if not run_cancelable([FFMPEG, "-y", "-threads", "2",
                    "-t", str(chunk), "-i", vpath,
                    "-vf", vf_pal, "-frames:v", "1", "-update", "1", pal],
                    cancel_event):
            return None
        if cancel_event and cancel_event.is_set():
            return None
        lavfi = f"{base_vf},{_paletteuse_filter(lossy)}"
        if not run_cancelable([FFMPEG, "-y", "-threads", "2",
                    "-t", str(chunk), "-i", vpath,
                    "-i", pal, "-lavfi", lavfi, raw], cancel_event):
            return None
        if GIFSICLE_MISSING:
            return os.path.getsize(raw) * (eff_dur / chunk) if os.path.exists(raw) else None
        if cancel_event and cancel_event.is_set():
            return None
        if not run_cancelable([GIFSICLE, f"--lossy={lossy}",
                    f"--colors={colors}", "-O3", raw, "-o", opt],
                    cancel_event):
            return os.path.getsize(raw) * (eff_dur / chunk) if os.path.exists(raw) else None
        target = opt if os.path.exists(opt) else raw
        return os.path.getsize(target) * (eff_dur / chunk)
    except Exception as e:
        print("estimate error:", e)
        return None
    finally:
        for f in (pal, raw, opt):
            try:
                if os.path.exists(f): os.remove(f)
            except: pass


def _convert_video(vpath, out_path, fmt,
                   fps, out_w, eff_dur, total_dur,
                   lossy, colors, sharpen, smooth,
                   effect="none", border=0, glow=0,
                   intensity=75, bloom=55, vignette=45, particles=45,
                   border_template=BORDER_TEMPLATE_NONE):
    td    = tempfile.gettempdir()
    # Sabit ad yerine çağrıya özgü benzersiz ad: iki GIF Maker penceresi/süreci
    # aynı anda dönüştürme yaparsa aynı geçici dosyaya çakışmasınlar.
    token = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    pal   = os.path.join(td, f"palette_full_{token}.png")
    raw   = os.path.join(td, f"raw_full_{token}.gif")
    base_vf = _video_filters(fps, out_w, sharpen, smooth, effect, border, glow,
                             intensity, bloom, vignette, particles)

    def dur_args():
        return ["-t", str(eff_dur)] if eff_dur < total_dur else []

    try:
        if fmt == "WebP":
            cmd = ([FFMPEG, "-y", "-threads", "6"]
                   + dur_args()
                   + ["-i", vpath, "-vf", base_vf,
                      "-loop", "0", "-q:v", "80", out_path])
            ok = run(cmd)
            if not ok:
                return False, "WebP dönüştürme hatası"
            _apply_border_template_to_output(out_path, "WebP", border_template, effect, glow,
                                             colors, lossy, eff_dur, fps)
            return True, "WebP hazır"

        # GIF: palettegen
        vf_pal = f"{base_vf},palettegen=max_colors={colors}:stats_mode=diff"
        if not run([FFMPEG, "-y", "-threads", "6"] + dur_args() +
                   ["-i", vpath, "-vf", vf_pal, "-frames:v", "1", "-update", "1", pal]):
            return False, "palettegen hatası"

        # GIF: paletteuse
        lavfi = f"{base_vf},{_paletteuse_filter(lossy)}"
        if not run([FFMPEG, "-y", "-threads", "6"] + dur_args() +
                   ["-i", vpath, "-i", pal,
                    "-lavfi", lavfi, raw]):
            return False, "paletteuse hatası"

        # gifsicle optimize. Yoksa ffmpeg'in ürettiği GIF'i yine de çıktı yap.
        if GIFSICLE_MISSING:
            shutil.copyfile(raw, out_path)
            _apply_border_template_to_output(out_path, "GIF", border_template, effect, glow,
                                             colors, lossy, eff_dur, fps)
            return True, "GIF hazır (gifsicle yok, optimize edilmedi)"

        if not run([GIFSICLE, f"--lossy={lossy}",
                    f"--colors={colors}", "-O3", raw, "-o", out_path]):
            shutil.copyfile(raw, out_path)
            _apply_border_template_to_output(out_path, "GIF", border_template, effect, glow,
                                             colors, lossy, eff_dur, fps)
            return True, "GIF hazır (gifsicle optimize edemedi)"

        _apply_border_template_to_output(out_path, "GIF", border_template, effect, glow,
                                         colors, lossy, eff_dur, fps)
        return True, "GIF hazır"
    except Exception as e:
        return False, str(e)
    finally:
        for fp in (pal, raw):
            try:
                if os.path.exists(fp): os.remove(fp)
            except: pass


def main():
    preload = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    app = GifMaker(preload_path=preload)
    app.mainloop()


if __name__ == "__main__":
    main()
