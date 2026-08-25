"""steameditor.ui.components — Reusable UI components."""

from __future__ import annotations

import os
import platform
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import customtkinter as ctk
from PIL import Image

from steameditor.ui.design_system import (
    COLORS, SPACING, TYPO, RADIUS, SHADOWS,
    make_font, lerp_color, apply_theme, make_ctk_image,
)

if TYPE_CHECKING:
    from steameditor.core.models import Template


# ════════════════════════════════════════════════════════════════════
# AnimButton — Animated hover/press feedback
# ════════════════════════════════════════════════════════════════════

class AnimButton(ctk.CTkButton):
    """Button with smooth color transition on hover."""

    _ANIM_STEPS = 12
    _ANIM_MS = 10

    def __init__(
        self,
        master,
        nc: str = COLORS.bg_3,
        hc: str = COLORS.bg_4,
        ac: str = COLORS.accent,
        ahc: str = COLORS.accent_hover,
        variant: str = "default",
        **kw,
    ):
        self._nc = nc if variant != "accent" else ac
        self._hc = hc if variant != "accent" else ahc
        self._t = 0.0
        self._aid = None

        kw.setdefault("corner_radius", RADIUS.md)
        kw.setdefault("border_width", 0)
        kw.setdefault("text_color", COLORS.text_primary)
        kw.setdefault("font", make_font(TYPO.body_md))
        kw.setdefault("height", 36)

        super().__init__(master, fg_color=self._nc, hover_color=self._hc, **kw)

        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _anim(self, target: float):
        if self._aid:
            try:
                self.after_cancel(self._aid)
            except Exception:
                pass
        delta = (target - self._t) / self._ANIM_STEPS

        def tick(n=self._ANIM_STEPS):
            self._t = max(0.0, min(1.0, self._t + delta))
            try:
                self.configure(fg_color=lerp_color(self._nc, self._hc, self._t))
            except Exception:
                return
            if n > 1:
                self._aid = self.after(self._ANIM_MS, tick, n - 1)
            else:
                self._t = target

        tick()

    def _enter(self, _=None):
        self._anim(1.0)

    def _leave(self, _=None):
        self._anim(0.0)


# ════════════════════════════════════════════════════════════════════
# Utility Functions
# ════════════════════════════════════════════════════════════════════

def open_folder(path: str | Path):
    """Open folder in system file manager."""
    path = Path(path)
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.Popen(["open", str(path)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        from steameditor.services.log_service import get_logger
        get_logger("ui").error(f"[OPEN FOLDER ERR] {e}")


# ════════════════════════════════════════════════════════════════════
# DropZone — Drag & drop + preview area
# ════════════════════════════════════════════════════════════════════

class DropZone(ctk.CTkFrame):
    """File drop zone with image preview."""

    def __init__(
        self,
        master,
        on_file: Callable[[str], None],
        on_batch: Optional[Callable[[list[str]], None]] = None,
        initialdir_getter: Optional[Callable[[], str]] = None,
        **kw,
    ):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=COLORS.bg_2, border_color=COLORS.border_default, **kw)

        self._on_file = on_file
        self._on_batch = on_batch
        self._initialdir_getter = initialdir_getter
        self._pulse_id = None
        self._pulse_t = 0.0
        self._pulse_dir = 1

        # Idle state
        self._idle_frame = ctk.CTkFrame(self, fg_color="transparent")

        badge = ctk.CTkFrame(self._idle_frame, width=86, height=86, corner_radius=43, fg_color=COLORS.bg_3)
        badge.pack(pady=(10, 16))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="📂", font=ctk.CTkFont("Segoe UI Emoji", 36), text_color=COLORS.accent_hover).pack(expand=True)

        ctk.CTkLabel(self._idle_frame, text="Görseli buraya sürükle", font=make_font(TYPO.display_sm), text_color=COLORS.text_primary).pack()
        ctk.CTkLabel(self._idle_frame, text="veya tıklayıp dosya seç", font=make_font(TYPO.body_md), text_color=COLORS.text_muted).pack(pady=(3, 16))

        pill = ctk.CTkFrame(self._idle_frame, fg_color=COLORS.bg_3, corner_radius=12)
        pill.pack()
        ctk.CTkLabel(pill, text="PNG  ·  JPG  ·  WEBP  ·  GIF", font=make_font(TYPO.body_sm, weight="bold"), text_color=COLORS.text_muted).pack(padx=16, pady=6)

        # Tips
        tips = ctk.CTkFrame(self._idle_frame, fg_color="transparent")
        tips.pack(pady=(22, 0))
        ctk.CTkLabel(tips, text="İPUÇLARI", font=make_font(TYPO.caption, weight="bold"), text_color=COLORS.text_muted).pack()
        for line in (
            "🖱  Grid'i sürükle · köşeden boyutlandır",
            "🖱  Çift tık = Böl  ·  Sağ tık = Hizalama",
            "✏  Metin katmanını sürükleyerek yerleştir",
            "🎮  Canlı vitrin: bant sayısının yanındaki buton",
            "⌨  Ctrl+O aç  ·  Ctrl+Enter böl  ·  Esc geri",
        ):
            ctk.CTkLabel(tips, text=line, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(pady=1)

        self._idle_frame.pack(expand=True)

        # Preview
        self._preview_label = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._preview_info = ctk.CTkLabel(
            self, text="", font=make_font(TYPO.body_md, weight="bold"),
            text_color=COLORS.accent, fg_color=COLORS.bg_3, corner_radius=8, padx=10, pady=5
        )

        self._batch_badge = ctk.CTkLabel(
            self, text="", font=make_font(TYPO.body_md, weight="bold"),
            text_color=COLORS.bg_0, fg_color=COLORS.accent, corner_radius=10, padx=10, pady=4
        )

        self.bind("<Button-1>", self._pick, add="+")
        for w in self._idle_frame.winfo_children():
            w.bind("<Button-1>", self._pick, add="+")

        # Drag & drop
        try:
            from tkinterdnd2 import DND_FILES
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

        self._start_pulse()

    def _start_pulse(self):
        def tick():
            self._pulse_t += 0.025 * self._pulse_dir
            if self._pulse_t >= 1.0:
                self._pulse_t = 1.0
                self._pulse_dir = -1
            elif self._pulse_t <= 0.0:
                self._pulse_t = 0.0
                self._pulse_dir = 1
            try:
                bc = lerp_color(COLORS.border_default, COLORS.text_muted, self._pulse_t)
                self.configure(border_color=bc)
            except Exception:
                return
            self._pulse_id = self.after(50, tick)
        tick()

    def _stop_pulse(self):
        if self._pulse_id:
            try:
                self.after_cancel(self._pulse_id)
            except Exception:
                pass

    def _pick(self, _=None):
        from tkinter import filedialog
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
        try:
            raw = self.tk.splitlist(event.data)
        except Exception:
            raw = [event.data]
        paths = []
        for p in raw:
            p = p.strip().strip("{}")
            if os.path.isfile(p) or os.path.isdir(p):
                paths.append(p)
        if not paths:
            return
        files = [p for p in paths if os.path.isfile(p)]
        if len(files) > 1 and self._on_batch:
            self._on_batch(files)
        else:
            self._on_file(paths[0])

    def bind_preview_mouse(self, on_press, on_drag, on_release=None, on_double=None, on_context=None, on_wheel=None):
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
        self.configure(border_color=COLORS.accent)

    def reset(self):
        self._preview_label.pack_forget()
        self._preview_info.pack_forget()
        self._batch_badge.place_forget()
        self._idle_frame.pack(expand=True)
        self.configure(border_color=COLORS.border_default)
        self._pulse_t = 0.0
        self._pulse_dir = 1
        self._start_pulse()


# ════════════════════════════════════════════════════════════════════
# StatusBar — Bottom status with animated messages
# ════════════════════════════════════════════════════════════════════

class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("corner_radius", 8)
        super().__init__(master, fg_color=COLORS.bg_2, height=36, **kw)
        self.pack_propagate(False)

        self._dot = ctk.CTkLabel(self, text="●", font=make_font(TYPO.body_md), text_color=COLORS.success, width=20)
        self._dot.pack(side="left", padx=(12, 4))

        self._lbl = ctk.CTkLabel(self, text="Hazır", font=make_font(TYPO.body_md), text_color=COLORS.text_muted, anchor="w")
        self._lbl.pack(side="left", fill="x", expand=True)

        self._right = ctk.CTkLabel(self, text="", font=make_font(TYPO.code), text_color=COLORS.text_muted)
        self._right.pack(side="right", padx=12)

        self._fade_id = None

    def set(self, msg: str, color=COLORS.text_primary, dot=COLORS.success, auto_reset=True):
        if self._fade_id:
            try:
                self.after_cancel(self._fade_id)
            except Exception:
                pass
        self._dot.configure(text_color=dot)
        self._lbl.configure(text=msg, text_color=color)
        if auto_reset:
            self._fade_id = self.after(4000, self._fade_to_ready)

    def set_right(self, txt: str):
        self._right.configure(text=txt)

    def _fade_to_ready(self):
        self._lbl.configure(text="Hazır", text_color=COLORS.text_muted)
        self._dot.configure(text_color=COLORS.success)

    def busy(self, msg="İşleniyor..."):
        self.set(msg, COLORS.accent, COLORS.accent, auto_reset=False)

    def ok(self, msg):
        self.set(msg, COLORS.success, COLORS.success)

    def error(self, msg):
        self.set(msg, COLORS.error, COLORS.error)


# ════════════════════════════════════════════════════════════════════
# SplitPreview — Modern Post-split preview panel
# ════════════════════════════════════════════════════════════════════

class SplitPreview(ctk.CTkFrame):
    """Modern preview panel with grid/showcase views, selection management,
    keyboard shortcuts, context menus, and batch operations."""
    _THUMB_W = 140
    _THUMB_H = 200
    _CARD_W = 168
    _CARD_H = 360

    def __init__(
        self,
        master,
        on_back: Callable,
        on_open: Callable,
        on_rerun: Callable,
        on_clear: Callable,
        on_open_file: Callable,
        on_copy_path: Callable,
        on_delete_file: Callable,
        on_upload: Callable | None = None,
        on_selection_change: Callable[[list[int]], None] | None = None,
        **kw,
    ):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=COLORS.bg_2, border_color=COLORS.accent, **kw)

        self._on_upload = on_upload
        self._on_back = on_back
        self._on_open = on_open
        self._on_rerun = on_rerun
        self._on_clear = on_clear
        self._on_open_file = on_open_file
        self._on_copy_path = on_copy_path
        self._on_delete_file = on_delete_file
        self._on_selection_change = on_selection_change

        self._tk_imgs: list = []
        self._file_paths: list[str] = []
        self._card_widgets: list[ctk.CTkFrame] = []
        self._card_indices: list[int] = []
        self._selected_indices: set[int] = set()
        self._focused_index: int = -1
        self._showcase_mode = False
        self._parts_per_row = 5
        self._dragging_index: int | None = None
        self._drag_start_x = 0
        self._drag_placeholder: ctk.CTkFrame | None = None

        self._build_ui()
        self._bind_keys()

    def _build_ui(self):
        # Header bar
        hdr = ctk.CTkFrame(self, fg_color=COLORS.bg_3, corner_radius=0, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self._title_lbl = ctk.CTkLabel(
            hdr, text="", font=make_font(TYPO.heading_lg), text_color=COLORS.accent
        )
        self._title_lbl.pack(side="left", padx=16)

        # Selection toolbar (initially hidden)
        self._selection_toolbar = ctk.CTkFrame(hdr, fg_color="transparent")
        self._sel_count_lbl = ctk.CTkLabel(
            self._selection_toolbar, text="", font=make_font(TYPO.body_md, weight="bold"),
            text_color=COLORS.accent
        )
        self._sel_count_lbl.pack(side="left", padx=(0, 12))

        AnimButton(self._selection_toolbar, text="Tümünü Seç", nc=COLORS.bg_4, hc=COLORS.bg_5,
                   height=28, corner_radius=6, font=make_font(TYPO.body_sm),
                   text_color=COLORS.text_primary, command=self._select_all).pack(side="left", padx=2)
        AnimButton(self._selection_toolbar, text="Seçimi Kaldır", nc=COLORS.bg_4, hc=COLORS.bg_5,
                   height=28, corner_radius=6, font=make_font(TYPO.body_sm),
                   text_color=COLORS.text_primary, command=self._deselect_all).pack(side="left", padx=2)
        AnimButton(self._selection_toolbar, text="🗑 Seçilileri Sil", nc=COLORS.error, hc=COLORS.error_active,
                   height=28, corner_radius=6, font=make_font(TYPO.body_sm, weight="bold"),
                   text_color=COLORS.text_inverse, command=self._delete_selected).pack(side="left", padx=2)
        if self._on_upload:
            AnimButton(self._selection_toolbar, text="☁ Seçilileri Yükle", nc=COLORS.accent_active, hc=COLORS.accent,
                       height=28, corner_radius=6, font=make_font(TYPO.body_sm, weight="bold"),
                       text_color=COLORS.text_inverse, command=self._upload_selected).pack(side="left", padx=2)

        # Right side actions
        right_actions = ctk.CTkFrame(hdr, fg_color="transparent")
        right_actions.pack(side="right", padx=10, pady=6)

        AnimButton(right_actions, text="← Geri", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_muted, command=self._on_back).pack(side="right", padx=4)

        AnimButton(right_actions, text="Klasörde Aç", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_primary, command=self._on_open).pack(side="right", padx=4)

        AnimButton(right_actions, text="Yeniden İşle", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_md), text_color=COLORS.accent, command=self._on_rerun).pack(side="right", padx=4)

        AnimButton(right_actions, text="Son Çıktıyı Temizle", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_md), text_color=COLORS.error, command=self._clear_current).pack(side="right", padx=4)

        if self._on_upload:
            AnimButton(right_actions, text="☁ Steam'e Yükle", nc=COLORS.accent_active, hc=COLORS.accent, variant="accent",
                       height=28, corner_radius=6, font=make_font(TYPO.body_md, weight="bold"),
                       text_color=COLORS.text_inverse, command=self._on_upload).pack(side="right", padx=4)

        self._view_btn = AnimButton(right_actions, text="🎮 Vitrin", nc=COLORS.bg_3, hc=COLORS.info, height=28, corner_radius=6,
                                    font=make_font(TYPO.body_md), text_color=COLORS.text_primary, command=self._toggle_view)
        self._view_btn.pack(side="right", padx=4)

        # Grid view (horizontal scroll)
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", orientation="horizontal",
            scrollbar_button_color=COLORS.bg_4, scrollbar_button_hover_color=COLORS.accent
        )
        self._scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Showcase view
        self._showcase = ctk.CTkScrollableFrame(
            self, fg_color="transparent", scrollbar_button_color=COLORS.bg_4,
            scrollbar_button_hover_color=COLORS.accent
        )
        self._showcase_lbl = ctk.CTkLabel(self._showcase, text="", fg_color="transparent")
        self._showcase_lbl.pack(pady=4)

    def _bind_keys(self):
        """Bind global keyboard shortcuts (CTk bind_all yasak; üst pencereye bağla)."""
        try:
            target = self.winfo_toplevel()
        except Exception:
            return
        target.bind("<Delete>", lambda e: self._handle_delete_key())
        target.bind("<BackSpace>", lambda e: self._handle_delete_key())
        target.bind("<Return>", lambda e: self._handle_enter_key())
        target.bind("<space>", lambda e: self._handle_space_key())
        target.bind("<Escape>", lambda e: self._handle_escape_key())
        target.bind("<Control-a>", lambda e: self._select_all())
        target.bind("<Left>", lambda e: self._navigate(-1))
        target.bind("<Right>", lambda e: self._navigate(1))
        target.bind("<Up>", lambda e: self._navigate(-1))
        target.bind("<Down>", lambda e: self._navigate(1))
        target.bind("<Home>", lambda e: self._navigate_home())
        target.bind("<End>", lambda e: self._navigate_end())

    def _toggle_view(self):
        self._showcase_mode = not self._showcase_mode
        if self._showcase_mode:
            self._scroll.pack_forget()
            self._showcase.pack(fill="both", expand=True, padx=10, pady=10)
            self._view_btn.configure(text="▤ Parçalar")
            self._render_showcase()
            self._hide_selection_toolbar()
        else:
            self._showcase.pack_forget()
            self._scroll.pack(fill="both", expand=True, padx=10, pady=10)
            self._view_btn.configure(text="🎮 Vitrin")

    def _render_showcase(self):
        if not self._file_paths:
            self._showcase_lbl.configure(image=None, text="Gösterilecek parça yok")
            return
        try:
            from steameditor.core.processor import render_showcase_preview
            sim = render_showcase_preview(self._file_paths, self._parts_per_row)
            avail = max(400, self.winfo_width() - 60)
            if sim.width > avail:
                scale = avail / sim.width
                sim = sim.resize((avail, max(1, int(sim.height * scale))), Image.LANCZOS)
            ctk_img = make_ctk_image(sim)
            self._showcase_lbl.configure(image=ctk_img, text="")
            self._showcase_lbl._image = ctk_img
        except Exception as e:
            self._showcase_lbl.configure(image=None, text=f"Vitrin hatası: {e}")

    def load(self, file_paths: list, parts_per_row: int | None = None):
        """Load and display split parts."""
        self._clear_selection()
        for w in self._scroll.winfo_children():
            w.destroy()
        self._tk_imgs.clear()
        self._card_widgets.clear()
        self._card_indices.clear()
        self._file_paths = list(file_paths)
        if parts_per_row:
            self._parts_per_row = max(1, int(parts_per_row))

        n = len(file_paths)
        self._title_lbl.configure(text=f"✂  {n} parça oluşturuldu")
        if self._showcase_mode:
            self._render_showcase()

        for i, path in enumerate(file_paths):
            self._create_card(i, path)

        if self._file_paths:
            self._focused_index = 0
            self._update_focus()

    def _create_card(self, index: int, path: str):
        card = ctk.CTkFrame(
            self._scroll, fg_color=COLORS.bg_3, corner_radius=12,
            width=self._CARD_W, height=self._CARD_H
        )
        card.pack(side="left", anchor="n", padx=8, pady=8)
        card.pack_propagate(False)

        # Store index for reference
        card._split_index = index

        # Checkmark overlay (hidden by default)
        check_overlay = ctk.CTkFrame(card, fg_color=COLORS.accent, corner_radius=8, width=28, height=28)
        check_overlay.place(x=8, y=8)
        check_overlay.place_forget()
        check_lbl = ctk.CTkLabel(check_overlay, text="✓", font=make_font(TYPO.caption, weight="bold"),
                                 text_color=COLORS.text_inverse)
        check_lbl.place(relx=0.5, rely=0.5, anchor="center")
        card._check_overlay = check_overlay

        # Focus ring
        focus_ring = ctk.CTkFrame(card, fg_color="transparent", corner_radius=12, border_width=2, border_color=COLORS.accent)
        focus_ring.place(x=0, y=0, relwidth=1, relheight=1)
        focus_ring.lower()
        focus_ring.place_forget()
        card._focus_ring = focus_ring

        # Thumbnail
        try:
            img = Image.open(path)
            if path.lower().endswith(".gif"):
                img.seek(0)
            img = img.convert("RGBA")
            img.thumbnail((self._THUMB_W, self._THUMB_H), Image.LANCZOS)

            bg_color = tuple(int(COLORS.bg_3.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
            bg = Image.new("RGBA", img.size, bg_color)
            bg.paste(img, mask=img.split()[3])
            ctk_img = make_ctk_image(bg.convert("RGB"))
            self._tk_imgs.append(ctk_img)

            img_lbl = ctk.CTkLabel(card, image=ctk_img, text="", fg_color="transparent")
            img_lbl.pack(pady=(12, 6))
        except Exception:
            ctk.CTkLabel(card, text="?", font=make_font(TYPO.display_sm), text_color=COLORS.text_muted).pack(pady=30)

        # Index badge
        ctk.CTkLabel(card, text=f"#{index+1}", font=make_font(TYPO.code, weight="bold"), text_color=COLORS.accent).pack()

        # Filename
        fname = os.path.basename(path)
        short = fname if len(fname) <= 20 else fname[:17] + "…"
        ctk.CTkLabel(card, text=short, font=make_font(TYPO.body_sm), text_color=COLORS.text_muted,
                     wraplength=self._CARD_W - 16, justify="center").pack(pady=(0, 4))

        # File size
        try:
            kb = os.path.getsize(path) / 1024
            size_str = f"{kb:.0f} KB" if kb < 1024 else f"{kb/1024:.1f} MB"
        except Exception:
            size_str = ""
        if size_str:
            ctk.CTkLabel(card, text=size_str, font=make_font(TYPO.body_sm), text_color=COLORS.text_muted).pack(pady=(0, 8))

        # Actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(0, 8))
        for label, color, cmd_factory in [
            ("Aç", COLORS.text_primary, lambda p=path: self._on_open_file(p)),
            ("Kopyala", COLORS.text_primary, lambda p=path: self._on_copy_path(p)),
            ("Sil", COLORS.error, lambda p=path, idx=index: self._delete_single(idx)),
        ]:
            AnimButton(actions, text=label, nc=COLORS.bg_4, hc=COLORS.bg_5, height=24, corner_radius=6,
                       font=make_font(TYPO.body_sm), text_color=color, command=cmd_factory).pack(fill="x", pady=2)

        # Bind click events for selection
        def on_click(_e, idx=index, cd=card):
            self._on_card_click(idx, cd)

        def on_right_click(e, idx=index, cd=card):
            self._show_context_menu(e, idx, cd)

        for w in (card, *card.winfo_children()):
            try:
                w.bind("<Button-1>", on_click, add="+")
                w.bind("<Button-3>", on_right_click, add="+")
            except Exception:
                pass

        # Drag bindings
        card.bind("<ButtonPress-1>", lambda e, idx=index: self._on_drag_start(e, idx), add="+")
        card.bind("<B1-Motion>", lambda e, idx=index: self._on_drag_motion(e, idx), add="+")
        card.bind("<ButtonRelease-1>", lambda e, idx=index: self._on_drag_end(e, idx), add="+")

        self._card_widgets.append(card)
        self._card_indices.append(index)

    def _on_card_click(self, index: int, card: ctk.CTkFrame):
        """Handle card click for selection."""
        if index in self._selected_indices:
            self._deselect(index)
        else:
            self._select(index)
        self._focused_index = index
        self._update_focus()

    def _on_drag_start(self, event, index: int):
        if index not in self._selected_indices:
            self._clear_selection()
            self._select(index)
        self._dragging_index = index
        self._drag_start_x = event.x_root

    def _on_drag_motion(self, event, index: int):
        if self._dragging_index is None:
            return
        # Visual feedback during drag
        pass

    def _on_drag_end(self, event, index: int):
        if self._dragging_index is None:
            return
        # TODO: Implement reorder logic
        self._dragging_index = None

    def _show_context_menu(self, event, index: int, card: ctk.CTkFrame):
        """Show context menu on right-click."""
        menu = ctk.CTkMenu(self, tearoff=0)
        menu.add_command(label="Aç", command=lambda: self._on_open_file(self._file_paths[index]))
        menu.add_command(label="Kopyala", command=lambda: self._on_copy_path(self._file_paths[index]))
        menu.add_separator()
        if index in self._selected_indices:
            menu.add_command(label="Seçimi Kaldır", command=lambda: self._deselect(index))
        else:
            menu.add_command(label="Seç", command=lambda: self._select(index))
        menu.add_command(label="Tümünü Seç", command=self._select_all)
        menu.add_separator()
        menu.add_command(label="Sil", command=lambda: self._delete_single(index))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _select(self, index: int):
        if index < 0 or index >= len(self._card_widgets):
            return
        self._selected_indices.add(index)
        card = self._card_widgets[index]
        card._check_overlay.place(x=8, y=8)
        card.configure(border_color=COLORS.accent, border_width=2)
        self._update_selection_toolbar()

    def _deselect(self, index: int):
        if index not in self._selected_indices:
            return
        self._selected_indices.discard(index)
        card = self._card_widgets[index]
        card._check_overlay.place_forget()
        if self._focused_index != index:
            card.configure(border_color=COLORS.border_default, border_width=2)
        self._update_selection_toolbar()

    def _clear_selection(self):
        for idx in list(self._selected_indices):
            self._deselect(idx)
        self._selected_indices.clear()
        self._update_selection_toolbar()

    def _select_all(self):
        for i in range(len(self._card_widgets)):
            self._select(i)
        self._focused_index = len(self._card_widgets) - 1 if self._card_widgets else -1
        self._update_focus()

    def _deselect_all(self):
        self._clear_selection()

    def _delete_single(self, index: int):
        if index < 0 or index >= len(self._file_paths):
            return
        path = self._file_paths[index]
        self._on_delete_file(path)
        # Remove from internal lists
        self._file_paths.pop(index)
        # Rebuild UI
        self.load(self._file_paths, self._parts_per_row)

    def _delete_selected(self):
        if not self._selected_indices:
            return
        indices = sorted(self._selected_indices, reverse=True)
        for idx in indices:
            if idx < len(self._file_paths):
                self._on_delete_file(self._file_paths[idx])
                self._file_paths.pop(idx)
        self._clear_selection()
        self.load(self._file_paths, self._parts_per_row)

    def _upload_selected(self):
        if not self._selected_indices or not self._on_upload:
            return
        paths = [self._file_paths[i] for i in sorted(self._selected_indices) if i < len(self._file_paths)]
        if paths:
            self._on_upload(paths)

    def _update_selection_toolbar(self):
        count = len(self._selected_indices)
        if count > 0:
            self._sel_count_lbl.configure(text=f"{count} seçili")
            self._selection_toolbar.pack(side="left", padx=16)
        else:
            self._selection_toolbar.pack_forget()
        if self._on_selection_change:
            self._on_selection_change(sorted(self._selected_indices))

    def _hide_selection_toolbar(self):
        self._selection_toolbar.pack_forget()

    def _navigate(self, delta: int):
        if not self._card_widgets:
            return
        if self._focused_index == -1:
            self._focused_index = 0 if delta > 0 else len(self._card_widgets) - 1
        else:
            self._focused_index = max(0, min(len(self._card_widgets) - 1, self._focused_index + delta))
        self._update_focus()
        self._scroll_to_focused()

    def _navigate_home(self):
        if self._card_widgets:
            self._focused_index = 0
            self._update_focus()
            self._scroll_to_focused()

    def _navigate_end(self):
        if self._card_widgets:
            self._focused_index = len(self._card_widgets) - 1
            self._update_focus()
            self._scroll_to_focused()

    def _update_focus(self):
        for i, card in enumerate(self._card_widgets):
            if i == self._focused_index:
                card._focus_ring.place(x=0, y=0, relwidth=1, relheight=1)
                card.lift()
            else:
                card._focus_ring.place_forget()
                if i not in self._selected_indices:
                    card.configure(border_color=COLORS.border_default, border_width=2)

    def _scroll_to_focused(self):
        if 0 <= self._focused_index < len(self._card_widgets):
            card = self._card_widgets[self._focused_index]
            self.after(10, lambda: self._scroll._parent_canvas.xview_moveto(
                (card.winfo_x() - 10) / max(1, self._scroll._parent_canvas.winfo_width())
            ))

    def _handle_delete_key(self):
        if self._selected_indices:
            self._delete_selected()
        elif self._focused_index >= 0:
            self._delete_single(self._focused_index)

    def _handle_enter_key(self):
        if self._focused_index >= 0 and self._focused_index < len(self._file_paths):
            self._on_open_file(self._file_paths[self._focused_index])

    def _handle_space_key(self):
        if self._focused_index >= 0:
            idx = self._focused_index
            if idx in self._selected_indices:
                self._deselect(idx)
            else:
                self._select(idx)

    def _handle_escape_key(self):
        if self._selected_indices:
            self._clear_selection()
        else:
            self._deselect_all()
            self._focused_index = -1
            self._update_focus()

    def _clear_current(self):
        self._on_clear(list(self._file_paths))
        self._file_paths.clear()
        self.load([])


# ════════════════════════════════════════════════════════════════════
# FixedCropDialog — Manual crop with zoom/pan
# ════════════════════════════════════════════════════════════════════

class FixedCropDialog(ctk.CTkToplevel):
    """Manual crop dialog — fixed size, zoom + pan."""

    def __init__(self, master, image: Image.Image, target_w: int, target_h: int, title: str = "Crop"):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=COLORS.bg_1)
        self.image = image
        self.target_w = target_w
        self.target_h = target_h
        self.scale = 0.5
        self.min_scale = 0.15
        self.max_scale = 4.0
        self.result_bbox = None

        self.box_x = max(0, (image.width - target_w) / 2)
        self.box_y = max(0, (image.height - target_h) / 2)

        self.canvas = ctk.CTkCanvas(self, bg=COLORS.bg_0, cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.geometry("900x620")

        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_do)
        self.canvas.bind("<Button-1>", self._click)
        self.bind("<Return>", self._enter)
        self.bind("<Escape>", self._cancel)

        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.bind(f"<{key}>", lambda _e, dx=dx, dy=dy: self._nudge(dx, dy))
            self.bind(f"<Shift-{key}>", lambda _e, dx=dx, dy=dy: self._nudge(dx * 10, dy * 10))

        self.focus_force()

        hint = ctk.CTkLabel(self, text="Scroll → zoom  |  Orta tık → pan  |  Sol tık → taşı  |  Ok: 1px (Shift: 10px)  |  Enter → onayla",
                             font=make_font(TYPO.caption), text_color=COLORS.text_muted, fg_color=COLORS.bg_2)
        hint.pack(fill="x", pady=0)

        tools = ctk.CTkFrame(self, fg_color=COLORS.bg_2, corner_radius=0)
        tools.pack(fill="x")
        for label, anchor in [
            ("Sola", "left"), ("Ortala", "center"), ("Sağa", "right"),
            ("Yukarı", "top"), ("Dikey Orta", "middle"), ("Aşağı", "bottom"),
        ]:
            AnimButton(tools, text=label, nc=COLORS.bg_3, hc=COLORS.bg_4, height=26, corner_radius=6,
                       font=make_font(TYPO.body_sm), text_color=COLORS.text_muted,
                       command=lambda a=anchor: self._snap(a)).pack(side="left", padx=4, pady=5)

        self.rect_id = None
        self.tk_img = None
        self._redraw()

    def _redraw(self):
        w, h = self.image.size
        sw = max(1, int(w * self.scale))
        sh = max(1, int(h * self.scale))
        disp = self.image.resize((sw, sh), Image.LANCZOS)
        self.tk_img = ctk.CTkImage(light_image=disp, dark_image=disp, size=(sw, sh))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.configure(scrollregion=(0, 0, sw, sh))

        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1 = max(0, min(sw - tw, self.box_x * self.scale))
        y1 = max(0, min(sh - th, self.box_y * self.scale))

        self.canvas.create_rectangle(x1+2, y1+2, x1+tw+2, y1+th+2, outline="", fill="#050505")
        self.rect_id = self.canvas.create_rectangle(x1, y1, x1+tw, y1+th, outline=COLORS.accent, width=2, dash=(6, 3))

    def _wheel(self, e):
        delta = 0.12 if e.delta > 0 else -0.12
        ns = min(self.max_scale, max(self.min_scale, self.scale + delta))
        if abs(ns - self.scale) < 0.01:
            return
        cx = self.canvas.canvasx(e.x) / (self.image.width * self.scale)
        cy = self.canvas.canvasy(e.y) / (self.image.height * self.scale)
        self.scale = ns
        self._redraw()
        sw = self.image.width * ns
        sh = self.image.height * ns
        self.canvas.xview_moveto((cx * sw - e.x) / sw)
        self.canvas.yview_moveto((cy * sh - e.y) / sh)

    def _pan_start(self, e):
        self.canvas.scan_mark(e.x, e.y)

    def _pan_do(self, e):
        self.canvas.scan_dragto(e.x, e.y, gain=1)

    def _click(self, e):
        if not self.rect_id:
            return
        cx = self.canvas.canvasx(e.x)
        cy = self.canvas.canvasy(e.y)
        sw = self.image.width * self.scale
        sh = self.image.height * self.scale
        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1 = max(0, min(sw - tw, cx - tw/2))
        y1 = max(0, min(sh - th, cy - th/2))
        self.canvas.coords(self.rect_id, x1, y1, x1+tw, y1+th)
        self.box_x = x1 / self.scale
        self.box_y = y1 / self.scale

    def _nudge(self, dx: int, dy: int):
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

    def _snap(self, anchor: str):
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


# ════════════════════════════════════════════════════════════════════
# TemplateCard — Template selector card
# ════════════════════════════════════════════════════════════════════

class TemplateCard(ctk.CTkFrame):
    _ANIM_STEPS = 10
    _ANIM_MS = 12

    def __init__(self, master, template, on_select, **kw):
        kw.setdefault("corner_radius", 10)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=COLORS.bg_3, border_color=COLORS.border_default, **kw)

        self.tmpl = template
        self._on_select = on_select
        self._selected = False
        self._t = 0.0
        self._aid = None

        icons = {"uniform": "⚡", "multi": "✏️", "single": "🖼"}
        icon = icons.get(template.mode, "◆")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=11, pady=(10, 2))

        ctk.CTkLabel(top, text=icon, font=ctk.CTkFont("Segoe UI Emoji", 16), text_color=COLORS.accent, width=22).pack(side="left", anchor="n")
        ctk.CTkLabel(top, text=template.name, font=make_font(TYPO.heading_md), text_color=COLORS.text_primary, wraplength=138, justify="left").pack(side="left", padx=(7, 0), anchor="n")

        info = self._info_text(template)
        ctk.CTkLabel(self, text=info, font=make_font(TYPO.caption), text_color=COLORS.text_muted, justify="left", wraplength=176).pack(anchor="w", padx=14, pady=(0, 9))

        for w in (self, *self.winfo_children()):
            try:
                w.bind("<Button-1>", self._click, add="+")
                w.bind("<Enter>", self._hover, add="+")
                w.bind("<Leave>", self._unhover, add="+")
            except Exception:
                pass

    def _info_text(self, t):
        m = t.mode
        if m == "uniform":
            bounds = self._uniform_bounds(t.width, t.parts if isinstance(t.parts, int) else 5)
            pw = bounds[0][1] - bounds[0][0]
            base = f"{t.parts if isinstance(t.parts, int) else 5} parça · {pw}px × {t.height}px"
            return base + ("  ·  Patch ✓" if t.patch else "")
        if m == "multi":
            parts = t.parts if isinstance(t.parts, list) else []
            widths = " + ".join(f"{p['width']}px" for p in parts)
            max_h = max((p["height"] for p in parts), default=0)
            return f"{widths} · {len(parts)} parça · {max_h}px yüksek"
        if m == "single":
            return f"{t.width}×{t.height}px · tek parça"
        return ""

    def _uniform_bounds(self, w, parts):
        parts = max(1, int(parts))
        base = w // parts
        rem = w % parts
        bounds = []
        x = 0
        for i in range(parts):
            w = base + (1 if i < rem else 0)
            bounds.append((x, x + w))
            x += w
        return bounds

    def _click(self, _=None):
        self._on_select(self.tmpl)

    def _hover(self, _=None):
        if not self._selected:
            self.configure(fg_color=COLORS.bg_4)

    def _unhover(self, _=None):
        if not self._selected:
            self.configure(fg_color=COLORS.bg_3)

    def set_selected(self, val: bool):
        self._selected = val
        target = 1.0 if val else 0.0
        if self._aid:
            try:
                self.after_cancel(self._aid)
            except Exception:
                pass
        delta = (target - self._t) / self._ANIM_STEPS

        def tick(n=self._ANIM_STEPS):
            self._t = max(0.0, min(1.0, self._t + delta))
            bc = lerp_color(COLORS.border_default, COLORS.accent, self._t)
            bg = lerp_color(COLORS.bg_3, "#2a2018", self._t)
            try:
                self.configure(border_color=bc, fg_color=bg)
            except Exception:
                return
            if n > 1:
                self._aid = self.after(self._ANIM_MS, tick, n - 1)
            else:
                self._t = target

        tick()

# ════════════════════════════════════════════════════════════════════
# TemplateSuggestionPanel — AI-powered template recommendations
# ════════════════════════════════════════════════════════════════════

class TemplateSuggestionPanel(ctk.CTkFrame):
    """Panel showing AI-recommended templates for the current image."""

    def __init__(
        self,
        master,
        on_select: Callable[[Template], None],
        on_apply: Callable[[Template], None],
        **kw,
    ):
        kw.setdefault("corner_radius", 12)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=COLORS.bg_2, border_color=COLORS.border_default, **kw)

        self._on_select = on_select
        self._on_apply = on_apply
        self._current_image: Image.Image | None = None
        self._matcher = None
        self._templates = []
        self._cards: list = []

        self.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="🤖  Şablon Önerileri", font=make_font(TYPO.heading_md), text_color=COLORS.accent).grid(row=0, column=0, sticky="w")

        self._refresh_btn = AnimButton(hdr, text="🔄 Yenile", nc=COLORS.bg_4, hc=COLORS.bg_5, height=26, corner_radius=6,
                                       font=make_font(TYPO.body_sm), text_color=COLORS.text_primary, command=self._refresh)
        self._refresh_btn.grid(row=0, column=1, sticky="e")

        # Scrollable suggestions list
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
            scrollbar_button_color=COLORS.bg_4, scrollbar_button_hover_color=COLORS.accent)
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Placeholder
        self._placeholder = ctk.CTkLabel(self._scroll, text="Bir görsel yüklendiğinde öneriler görünecek",
                                         font=make_font(TYPO.body_md), text_color=COLORS.text_muted)
        self._placeholder.grid(row=0, column=0, pady=40)

    def set_image(self, image: Image.Image):
        """Update suggestions based on new source image."""
        self._current_image = image
        self._refresh()

    def _refresh(self):
        if self._current_image is None:
            return

        # Lazy import to avoid circular
        if self._matcher is None:
            from steameditor.core.template_matcher import TemplateMatcher
            from steameditor.core.models import BUILTIN_TEMPLATES
            self._matcher = TemplateMatcher()
            self._templates = BUILTIN_TEMPLATES

        matches = self._matcher.match(self._current_image, self._templates)

        # Clear old cards
        for card in self._cards:
            card.destroy()
        self._cards.clear()
        self._placeholder.grid_remove()

        if not matches:
            self._placeholder.configure(text="Uygun şablon bulunamadı")
            self._placeholder.grid(row=0, column=0, pady=40)
            return

        for i, match in enumerate(matches[:5]):  # Top 5
            card = self._create_suggestion_card(match, i)
            card.grid(row=i, column=0, sticky="ew", pady=4)
            self._cards.append(card)

    def _create_suggestion_card(self, match, index: int) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self._scroll, fg_color=COLORS.bg_3, corner_radius=10, border_width=2,
                            border_color=COLORS.accent if index == 0 else COLORS.border_default)
        card.grid_columnconfigure(1, weight=1)

        # Confidence badge
        conf_colors = {"high": COLORS.success, "medium": COLORS.warning, "low": COLORS.text_muted}
        conf_text = {"high": "🟢 Yüksek", "medium": "🟡 Orta", "low": "🔴 Düşük"}
        badge = ctk.CTkLabel(card, text=conf_text.get(match.confidence, match.confidence),
                             font=make_font(TYPO.caption, weight="bold"), text_color=conf_colors.get(match.confidence, COLORS.text_primary),
                             fg_color=COLORS.accent_subtle, corner_radius=4, padx=8, pady=2)
        badge.grid(row=0, column=0, rowspan=3, padx=(10, 8), pady=10, sticky="n")

        # Template info
        tmpl = match.template
        icons = {"uniform": "⚡", "multi": "✏️", "single": "🖼"}
        icon = icons.get(tmpl.mode, "◆")

        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont("Segoe UI Emoji", 24), text_color=COLORS.accent).grid(row=0, column=1, sticky="w", pady=(8, 0))
        ctk.CTkLabel(card, text=tmpl.name, font=make_font(TYPO.heading_sm), text_color=COLORS.text_primary, wraplength=300).grid(row=1, column=1, sticky="w", padx=(8, 10))

        # Score + reasons
        score_pct = int(match.score * 100)
        reasons_text = " · ".join(match.reasons[:3]) if match.reasons else "Genel uyum"
        ctk.CTkLabel(card, text=f"Uyum: %{score_pct}  —  {reasons_text}",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted, wraplength=300).grid(row=2, column=1, sticky="w", padx=(8, 10), pady=(0, 8))

        # Dimensions
        if tmpl.mode == "uniform":
            dim_text = f"⚡ {tmpl.width}×{tmpl.height}px  ·  {tmpl.parts} parça"
        elif tmpl.mode == "multi":
            parts = tmpl.parts if isinstance(tmpl.parts, list) else []
            dim_text = f"✏️ {len(parts)} parça  ·  Toplam {sum(p.width for p in parts)}×{max(p.height for p in parts)}px"
        else:
            dim_text = f"🖼 {tmpl.width}×{tmpl.height}px  ·  Tek parça"
        ctk.CTkLabel(card, text=dim_text, font=make_font(TYPO.caption), text_color=COLORS.text_muted).grid(row=3, column=1, sticky="w", padx=(8, 10), pady=(0, 8))

        # Actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=4, padx=10, pady=8, sticky="ns")

        AnimButton(actions, text="Seç", variant="accent", height=30, text_color=COLORS.bg_0,
                   command=lambda m=match: self._on_select(m.template)).pack(pady=2)
        AnimButton(actions, text="Uygula", nc=COLORS.bg_4, hc=COLORS.bg_5, height=28, corner_radius=6,
                   font=make_font(TYPO.body_sm), text_color=COLORS.text_primary,
                   command=lambda m=match: self._on_apply(m.template)).pack(pady=2)

        return card


# ════════════════════════════════════════════════════════════════════
# LiveShowcaseDialog — Steam Profile Showcase Simulator
# ════════════════════════════════════════════════════════════════════

class LiveShowcaseDialog(ctk.CTkToplevel):
    """Full-screen Steam profile showcase simulator with multiple display modes."""

    SHOWCASE_TYPES = {
        "artwork": {"name": "🎨 Sanat Eseri Vitrini", "cols": 1, "ratio": 0.506, "desc": "Dikey sanat eseri (506×1000)"},
        "workshop": {"name": "⚙️ Atölye Vitrini (5-Parça)", "cols": 5, "ratio": 0.603, "desc": "Yatay 5-parça vitrin (754×1250)"},
        "screenshot": {"name": "📸 Ekran Görüntüsü Vitrini", "cols": 1, "ratio": 0.65, "desc": "Tek parça ekran görüntüsü (650×1000)"},
    }

    def __init__(self, master, piece_paths: list[str], current_template: str = "workshop", **kw):
        super().__init__(master)
        self.title("🎮 Canlı Steam Vitrin Simülatörü")
        self.geometry("1100x750")
        self.minsize(900, 600)
        self.configure(fg_color=COLORS.bg_0)

        self._piece_paths = list(piece_paths)
        self._current_type = current_template
        self._tk_images: list = []
        self._bg_image = None
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_start = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS.bg_1, corner_radius=0, height=56)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="🎮  Steam Profil Vitrin Simülatörü", font=make_font(TYPO.heading_lg), text_color=COLORS.accent).grid(row=0, column=0, padx=16, pady=12, sticky="w")

        # Showcase type selector
        type_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        type_frame.grid(row=0, column=1, sticky="e", padx=16)
        ctk.CTkLabel(type_frame, text="Tür:", font=make_font(TYPO.body_sm), text_color=COLORS.text_muted).pack(side="left", padx=(0, 8))

        self._type_var = ctk.StringVar(value=self.SHOWCASE_TYPES[current_template]["name"])
        self._type_menu = ctk.CTkOptionMenu(type_frame, values=[v["name"] for v in self.SHOWCASE_TYPES.values()],
                                            variable=self._type_var, fg_color=COLORS.bg_3, button_color=COLORS.accent,
                                            button_hover_color=COLORS.accent_hover, text_color=COLORS.text_primary,
                                            font=make_font(TYPO.body_sm), width=220, command=self._on_type_change)
        self._type_menu.pack(side="left", padx=(0, 8))

        # Controls
        ctrl_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        ctrl_frame.grid(row=0, column=2, padx=16)

        AnimButton(ctrl_frame, text="🔍 Yakınlaştır", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_sm), text_color=COLORS.text_primary, command=self._zoom_in).pack(side="left", padx=2)
        AnimButton(ctrl_frame, text="🔎 Uzaklaştır", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_sm), text_color=COLORS.text_primary, command=self._zoom_out).pack(side="left", padx=2)
        AnimButton(ctrl_frame, text="🏠 Sıfırla", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_sm), text_color=COLORS.text_primary, command=self._reset_view).pack(side="left", padx=2)
        AnimButton(ctrl_frame, text="✕ Kapat", nc=COLORS.error, hc=COLORS.error_active, height=28, corner_radius=6,
                   font=make_font(TYPO.body_sm, weight="bold"), text_color=COLORS.text_inverse, command=self.destroy).pack(side="left", padx=(8, 0))

        # Main canvas area
        canvas_frame = ctk.CTkFrame(self, fg_color=COLORS.bg_0, corner_radius=0)
        canvas_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)

        self._canvas = ctk.CTkCanvas(canvas_frame, bg=COLORS.bg_0, highlightthickness=0, cursor="fleur")
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbars
        h_scroll = ctk.CTkScrollbar(canvas_frame, orientation="horizontal", command=self._canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll = ctk.CTkScrollbar(canvas_frame, orientation="vertical", command=self._canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")

        self._canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        # Bindings
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Button-4>", self._on_wheel)
        self._canvas.bind("<Button-5>", self._on_wheel)
        self._canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self._canvas.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Control-plus>", lambda _: self._zoom_in())
        self.bind("<Control-minus>", lambda _: self._zoom_out())
        self.bind("<Control-0>", lambda _: self._reset_view())

        # Info bar at bottom
        info_frame = ctk.CTkFrame(self, fg_color=COLORS.bg_1, corner_radius=0, height=40)
        info_frame.grid(row=2, column=0, sticky="ew")
        info_frame.grid_propagate(False)
        info_frame.grid_columnconfigure(1, weight=1)

        self._info_lbl = ctk.CTkLabel(info_frame, text="", font=make_font(TYPO.caption), text_color=COLORS.text_muted)
        self._info_lbl.grid(row=0, column=0, padx=16, pady=8, sticky="w")

        self._piece_info = ctk.CTkLabel(info_frame, text="", font=make_font(TYPO.caption), text_color=COLORS.accent)
        self._piece_info.grid(row=0, column=2, padx=16, pady=8, sticky="e")

        self.focus_force()
        self._render()

    def _on_type_change(self, value: str):
        for key, info in self.SHOWCASE_TYPES.items():
            if info["name"] == value:
                self._current_type = key
                break
        self._render()

    def _get_showcase_info(self) -> dict:
        return self.SHOWCASE_TYPES.get(self._current_type, self.SHOWCASE_TYPES["workshop"])

    def _render(self):
        """Render the showcase simulation."""
        self._canvas.delete("all")
        self._tk_images.clear()

        if not self._piece_paths:
            self._canvas.create_text(400, 300, text="Parça yok — önce bölme işlemi yapın",
                                     fill=COLORS.text_muted, font=make_font(TYPO.body_md))
            return

        info = self._get_showcase_info()
        cols = info["cols"]
        piece_count = len(self._piece_paths)

        # Steam profile background (dark theme)
        profile_bg = (23, 26, 33)  # Steam dark blue
        gap = 4  # Steam's gap between pieces

        # Calculate cell size based on first piece aspect ratio
        first_img = Image.open(self._piece_paths[0])
        if first_img.height > 0:
            cell_aspect = first_img.width / first_img.height
        else:
            cell_aspect = info["ratio"]

        # Target cell width for display
        target_cell_w = 180
        target_cell_h = int(target_cell_w / cell_aspect)

        # Canvas size
        rows = (piece_count + cols - 1) // cols
        canvas_w = cols * target_cell_w + (cols - 1) * gap + 40  # padding
        canvas_h = rows * target_cell_h + (rows - 1) * gap + 120  # extra for profile header

        self._canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))

        # Draw profile background
        self._canvas.create_rectangle(0, 0, canvas_w, canvas_h, fill=f"#{profile_bg[0]:02x}{profile_bg[1]:02x}{profile_bg[2]:02x}", outline="")

        # Profile header area (simulated)
        header_h = 80
        self._canvas.create_rectangle(0, 0, canvas_w, header_h, fill="#1b1d23", outline="")
        # Avatar placeholder
        self._canvas.create_oval(20, 10, 70, 60, fill="#2a2d35", outline="#4a4d55", width=2)
        self._canvas.create_text(45, 35, text="👤", fill=COLORS.text_muted, font=("Segoe UI Emoji", 20))
        # Username placeholder
        self._canvas.create_text(90, 25, text="Steam Kullanıcı", fill=COLORS.text_primary, font=("Segoe UI", 14, "bold"), anchor="w")
        self._canvas.create_text(90, 50, text=f"Vitrin: {info['name']}", fill=COLORS.text_muted, font=("Segoe UI", 11), anchor="w")

        # Draw pieces in grid
        start_y = header_h + 20
        for i, path in enumerate(self._piece_paths):
            row = i // cols
            col = i % cols
            x = 20 + col * (target_cell_w + gap)
            y = start_y + row * (target_cell_h + gap)

            try:
                img = Image.open(path)
                if path.lower().endswith(".gif"):
                    img.seek(0)
                img = img.convert("RGBA")

                # Resize to fit cell maintaining aspect
                img_ratio = img.width / img.height
                if img_ratio > cell_aspect:
                    # Wider than cell - fit width
                    new_w = target_cell_w
                    new_h = int(target_cell_w / img_ratio)
                else:
                    # Taller than cell - fit height
                    new_h = target_cell_h
                    new_w = int(target_cell_h * img_ratio)

                img = img.resize((new_w, new_h), Image.LANCZOS)

                # Center in cell
                offset_x = (target_cell_w - new_w) // 2
                offset_y = (target_cell_h - new_h) // 2

                # Cell background (Steam style)
                self._canvas.create_rectangle(x, y, x + target_cell_w, y + target_cell_h,
                                              fill="#1b1d23", outline="#3a3d45", width=1)

                # Paste image
                ctk_img = make_ctk_image(img.convert("RGB"))
                self._tk_images.append(ctk_img)
                self._canvas.create_image(x + offset_x, y + offset_y, anchor="nw", image=ctk_img)

                # Piece number badge
                self._canvas.create_text(x + 8, y + 8, text=f"#{i+1}", fill=COLORS.accent,
                                         font=make_font(TYPO.caption, weight="bold"), anchor="nw")

            except Exception as e:
                self._canvas.create_rectangle(x, y, x + target_cell_w, y + target_cell_h,
                                              fill="#1b1d23", outline="#3a3d45", width=1)
                self._canvas.create_text(x + target_cell_w//2, y + target_cell_h//2, text=f"⚠\n{e}",
                                         fill=COLORS.error, font=make_font(TYPO.caption), anchor="center")

        # Update info labels
        self._info_lbl.configure(text=f"Parça sayısı: {piece_count}  |  Grid: {cols} sütun × {rows} satır  |  Boşluk: {gap}px  |  Steam profil arka planı simülasyonu")
        self._piece_info.configure(text=f"Tür: {info['name']}  —  {info['desc']}")

    def _on_wheel(self, event):
        if event.delta > 0 or event.num == 4:
            self._zoom_in()
        else:
            self._zoom_out()

    def _zoom_in(self):
        self._zoom = min(3.0, self._zoom * 1.2)
        self._canvas.scale("all", 0, 0, 1.2, 1.2)
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _zoom_out(self):
        self._zoom = max(0.3, self._zoom / 1.2)
        self._canvas.scale("all", 0, 0, 1/1.2, 1/1.2)
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _reset_view(self):
        self._zoom = 1.0
        self._canvas.xview_moveto(0)
        self._canvas.yview_moveto(0)

    def _on_drag_start(self, event):
        self._canvas.scan_mark(event.x, event.y)
        self._drag_start = (event.x, event.y)

    def _on_drag(self, event):
        self._canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_drag_end(self, event):
        self._drag_start = None

    def _on_double_click(self, event):
        # Reset zoom on double-click
        self._reset_view()


# ════════════════════════════════════════════════════════════════════
# EXPORTS
# ════════════════════════════════════════════════════════════════════

__all__ = [
    "AnimButton",
    "DropZone",
    "StatusBar",
    "SplitPreview",
    "FixedCropDialog",
    "TemplateCard",
    "TemplateSuggestionPanel",
    "LiveShowcaseDialog",
]