"""ui_theme.py — ortak tema katmanı: renk paleti, renk araçları,
make_ctk_image ve AnimButton. editor.py ve ui_settings.py buradan import eder.
"""
import customtkinter as ctk
from PIL import Image

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


def make_ctk_image(img: Image.Image, size: tuple[int, int] | None = None) -> ctk.CTkImage:
    """PIL görselini CustomTkinter HighDPI uyumlu görsele çevirir."""
    if size is None:
        size = img.size
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)
