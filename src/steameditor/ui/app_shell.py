"""steameditor.ui.app_shell — Modern AppShell with workspace layout."""

from __future__ import annotations

import os
import sys
import json
import time
import platform
import threading
import webbrowser
import subprocess
import shutil
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from tkinter import filedialog, messagebox, Text, BooleanVar, StringVar, Menu, Toplevel, Canvas
from PIL import Image, ImageTk, ImageSequence, ImageDraw, ImageFilter

import customtkinter as ctk

from steameditor.core import (
    process_image, split_gif_frames, process_folder,
    manual_crop_with_template, uniform_slice_bounds,
    render_template_preview, template_output_summary,
    render_showcase_preview, open_folder,
    apply_text_overlay, text_overlay_bbox,
    _apply_effects_pipeline, autocrop_borders,
    list_border_templates, find_gifsicle, optimize_gif_file,
    patch_gif_trailing_byte, patch_png_last_byte,
    resize_cover, save_output_piece,
)
from steameditor.core.models import (
    Template, EffectConfig, ProcessingContext, ProcessingResult,
    BUILTIN_TEMPLATES, DEFAULT_TEMPLATE,
)
from steameditor.services import (
    get_config_service, get_worker_pool, get_event_bus,
    get_image_cache, get_thumbnail,
)
from steameditor.services.flat_config import FlatConfig
from steameditor.events import emit, subscribe
from steameditor.ui.design_system import (
    apply_theme, make_ctk_image, COLORS, TYPO, RADIUS, make_font, lerp_color,
    get_theme, set_theme, toggle_theme,
)
from steameditor.ui.components import (
    AnimButton, DropZone, StatusBar, SplitPreview,
    TemplateSuggestionPanel,
)
from steameditor.ui.pages.settings_page import SettingsPage
from steameditor.exceptions import handle_exception, SteamEditorError

# ─── Constants ───
F12_ARMED = False


# ─── Helper: ctkFont alias ───
def ctkFont(family: str, size: int, weight: str = "normal"):
    return ctk.CTkFont(family, size, weight)


# ─── TemplateCard ───
class TemplateCard(ctk.CTkFrame):
    _N = 10
    _MS = 12

    def __init__(self, master, template, on_select, **kw):
        kw.setdefault("corner_radius", RADIUS.lg)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=COLORS.surface_2, border_color=COLORS.border_default, **kw)
        self.tmpl = template
        self._on_select = on_select
        self._selected = False
        self._t = 0.0
        self._aid = None

        icons = {"uniform": "⚡", "multi": "✏️", "single": "🖼"}
        icon = icons.get(template.mode, "◆")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=11, pady=(10, 2))

        ctk.CTkLabel(top, text=icon, font=ctkFont("Segoe UI Emoji", 16), text_color=COLORS.accent_500, width=22).pack(side="left", anchor="n")
        ctk.CTkLabel(top, text=template.name, font=make_font(TYPO.heading_sm), text_color=COLORS.text_primary, wraplength=138, justify="left").pack(side="left", padx=(7, 0), anchor="n")

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
            bounds = uniform_slice_bounds(t.width, t.parts if isinstance(t.parts, int) else 5)
            pw = bounds[0][1] - bounds[0][0]
            base = f"{t.parts if isinstance(t.parts, int) else 5} parça · {pw}px × {t.height}px"
            return base + ("  ·  Patch ✓" if t.patch else "")
        if m == "multi":
            parts = t.parts if isinstance(t.parts, list) else []
            widths = " + ".join(f"{p.width}px" for p in parts)
            max_h = max((p.height for p in parts), default=0)
            return f"{widths} · {len(parts)} parça · {max_h}px yüksek"
        if m == "single":
            return f"{t.width}×{t.height}px · tek parça"
        return ""

    def _click(self, _=None):
        self._on_select(self.tmpl)

    def _hover(self, _=None):
        if not self._selected:
            self.configure(fg_color=COLORS.surface_3)

    def _unhover(self, _=None):
        if not self._selected:
            self.configure(fg_color=COLORS.surface_2)

    def set_selected(self, val: bool):
        self._selected = val
        target = 1.0 if val else 0.0
        if self._aid:
            try: self.after_cancel(self._aid)
            except: pass
        delta = (target - self._t) / self._N
        def tick(n=self._N):
            self._t = max(0.0, min(1.0, self._t + delta))
            bc = lerp_color(COLORS.border_default, COLORS.accent_500, self._t)
            bg = lerp_color(COLORS.surface_2, COLORS.surface_3, self._t)
            try:
                self.configure(border_color=bc, fg_color=bg)
            except: return
            if n > 1:
                self._aid = self.after(self._MS, tick, n-1)
            else:
                self._t = target
        tick()


# ─── FixedCropDialog ───
class FixedCropDialog(Toplevel):
    def __init__(self, master, image, target_w, target_h, title="Crop"):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=COLORS.surface_0)
        self.image = image
        self.target_w = target_w
        self.target_h = target_h
        self.scale = 0.5
        self.min_scale = 0.15
        self.max_scale = 4.0
        self.result_bbox = None

        self.box_x = max(0, (image.width - target_w) / 2)
        self.box_y = max(0, (image.height - target_h) / 2)

        self.canvas = Canvas(self, bg=COLORS.surface_0, cursor="crosshair", highlightthickness=0)
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

        hint = ctk.CTkLabel(self, text="Scroll → zoom   |   Orta tık → pan   |   Sol tık → kareyi taşı   |   Ok tuşları → 1px (Shift: 10px)   |   Enter → onayla",
                             font=make_font(TYPO.caption), text_color=COLORS.text_muted, fg_color=COLORS.surface_2)
        hint.pack(fill="x", pady=0)

        tools = ctk.CTkFrame(self, fg_color=COLORS.surface_2, corner_radius=0)
        tools.pack(fill="x")
        for label, anchor in [
            ("Sola", "left"), ("Ortala", "center"), ("Sağa", "right"),
            ("Yukarı", "top"), ("Dikey Orta", "middle"), ("Aşağı", "bottom"),
        ]:
            AnimButton(tools, text=label, nc=COLORS.surface_3, hc=COLORS.surface_4, height=26, corner_radius=6,
                       font=make_font(TYPO.caption), text_color=COLORS.text_muted,
                       command=lambda a=anchor: self._snap(a)).pack(side="left", padx=4, pady=5)

        self.rect_id = None
        self.tk_img = None
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
        self.canvas.create_rectangle(x1+2, y1+2, x1+tw+2, y1+th+2, outline="", fill="#050505")
        self.rect_id = self.canvas.create_rectangle(x1, y1, x1+tw, y1+th, outline=COLORS.accent_500, width=2, dash=(6, 3))

    def _wheel(self, e):
        delta = 0.12 if e.delta > 0 else -0.12
        ns = min(self.max_scale, max(self.min_scale, self.scale + delta))
        if abs(ns - self.scale) < 0.01: return
        cx = self.canvas.canvasx(e.x) / (self.image.width * self.scale)
        cy = self.canvas.canvasy(e.y) / (self.image.height * self.scale)
        self.scale = ns
        self._redraw()
        sw = self.image.width * ns
        sh = self.image.height * ns
        self.canvas.xview_moveto((cx * sw - e.x) / sw)
        self.canvas.yview_moveto((cy * sh - e.y) / sh)

    def _pan_start(self, e): self.canvas.scan_mark(e.x, e.y)
    def _pan_do(self, e): self.canvas.scan_dragto(e.x, e.y, gain=1)

    def _click(self, e):
        if not self.rect_id: return
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
        if not self.rect_id: return
        sw = self.image.width * self.scale
        sh = self.image.height * self.scale
        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1 = max(0, min(sw - tw, self.box_x * self.scale + dx))
        y1 = max(0, min(sh - th, self.box_y * self.scale + dy))
        self.canvas.coords(self.rect_id, x1, y1, x1+tw, y1+th)
        self.box_x = x1 / self.scale
        self.box_y = y1 / self.scale

    def _snap(self, anchor):
        if not self.rect_id: return
        sw = self.image.width * self.scale
        sh = self.image.height * self.scale
        tw = self.target_w * self.scale
        th = self.target_h * self.scale
        x1, y1, _, _ = self.canvas.coords(self.rect_id)
        if anchor == "center":
            x1, y1 = (sw - tw) / 2, (sh - th) / 2
        elif anchor == "top":
            y1 = 0
        elif anchor == "bottom":
            y1 = sh - th
        elif anchor == "left":
            x1 = 0
        elif anchor == "right":
            x1 = sw - tw
        self.canvas.coords(self.rect_id, x1, y1, x1+tw, y1+th)
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


# ─── Main App ───
class App(ctk.CTk):
    def __init__(self, preload_path=None):
        super().__init__()

        # DND setup
        self._dnd_ok = False
        try:
            import tkinterdnd2
            tkinterdnd2.TkinterDnD._require(self)
            self._dnd_ok = True
        except Exception as e:
            from steameditor.services.log_service import get_logger
            get_logger("app").warning(f"[DND] tkdnd yüklenemedi, sürükle-bırak devre dışı: {e}")

        self.title("SplitForge — Steam Showcase Studio")
        self.geometry("1340x840")
        self.minsize(1040, 700)
        self.configure(fg_color=COLORS.surface_0)
        self._apply_app_icon()

        self.current_path = None
        self._batch_files = None
        self._grid_pos = None
        self._grid_scale = 1.0
        self._live_showcase = False
        self._pv = None
        self._last_outputs = []
        self._splitting = False
        self._upload_proc = None
        self.template = DEFAULT_TEMPLATE
        self._cfg = FlatConfig(get_config_service().config)
        # Apply saved theme (default dark)
        try:
            set_theme(self._cfg.get("theme", "dark"))
        except Exception:
            pass
        saved_out = self._cfg["output_dir"]
        _default_out = Path(__file__).parent.parent.parent / "output"
        self.output_dir = Path(saved_out) if saved_out and Path(saved_out).is_dir() else _default_out
        default_name = self._cfg["default_preset"]
        for t in BUILTIN_TEMPLATES:
            if t.name == default_name:
                self.template = t
                break

        self._build()

        # Shortcuts
        self.bind("<Control-o>", lambda _e: self._pick_file())
        self.bind("<Control-Return>", lambda _e: self._split_single())
        self.bind("<Control-t>", lambda _e: self._toggle_theme())
        self.bind("<Control-T>", lambda _e: self._toggle_theme())
        self.bind("<Escape>", self._on_escape)

        # Recovery
        self._last_recovery_state = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(30000, self._recovery_tick)

        if preload_path and os.path.isfile(preload_path):
            self.after(200, lambda: self._on_file_drop(preload_path))
        else:
            self.after(400, self._offer_recovery)

    def _apply_app_icon(self):
        root = Path(__file__).parent.parent.parent
        ico = root / "app_icon.ico"
        png = root / "app_icon.png"
        if ico.is_file():
            try: self.iconbitmap(ico)
            except: pass
        if png.is_file():
            try:
                self._icon_photo = ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_photo)
                self._logo_img = make_ctk_image(Image.open(png).resize((34, 34), Image.LANCZOS))
            except: self._logo_img = None

    # ─── Build ───
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_settings_page()

    def _build_settings_page(self):
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

    # ─── Recovery ───
    def _recovery_snapshot(self) -> dict | None:
        if not self.current_path and not self._batch_files:
            return None
        state = {"template_name": self.template.name, "timestamp": time.time()}
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
                comparable = {k: v for k, v in state.items() if k != "timestamp"}
                if comparable != self._last_recovery_state:
                    get_config_service().save_recovery(state)
                    self._last_recovery_state = comparable
        except Exception as e:
            from steameditor.services.log_service import get_logger
            get_logger("recovery").error(f"[RECOVERY TICK ERR] {e}")
        self.after(30000, self._recovery_tick)

    def _offer_recovery(self):
        state = get_config_service().load_recovery()
        if not state:
            return
        paths = state.get("input_paths") or []
        input_dir = state.get("input_dir", "")
        valid_paths = [p for p in paths if os.path.isfile(p)]
        if not valid_paths and not (input_dir and os.path.isdir(input_dir)):
            get_config_service().clear_recovery()
            return
        desc = (os.path.basename(input_dir) + " (klasör)") if input_dir else (
            os.path.basename(valid_paths[0]) + (f" +{len(valid_paths) - 1} dosya" if len(valid_paths) > 1 else ""))
        if not messagebox.askyesno("Kaldığın Yerden Devam",
                f"Son oturum düzgün kapanmamış görünüyor.\n\nÜzerinde çalıştığın iş geri yüklensin mi?\n• {desc}"):
            get_config_service().clear_recovery()
            return
        tmpl = next((t for t in BUILTIN_TEMPLATES if t.name == state.get("template_name")), None)
        if tmpl:
            self.template = tmpl
            self._sync_cards()
            self._status.set_right(tmpl.name)
        if input_dir and os.path.isdir(input_dir):
            self._on_file_drop(input_dir)
        elif len(valid_paths) > 1:
            self._on_batch_drop(valid_paths)
        else:
            self._on_file_drop(valid_paths[0])
        self._status.ok("Çalışma geri yüklendi ✓")

    def _on_close(self):
        get_config_service().clear_recovery()
        self.destroy()

    def _on_escape(self, _=None):
        if self._settings_page.grid_info():
            self._settings_page._back()
        elif self._split_prev.grid_info():
            self._back_to_drop()

    def _notify_attention(self):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            try: self.bell()
            except: pass
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2)
            ctypes.windll.user32.FlashWindow(hwnd, True)
        except Exception:
            pass

    # ─── Sidebar ───
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=280, fg_color=COLORS.surface_1, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew", rowspan=2)
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(2, weight=1)

        # Logo
        logo_f = ctk.CTkFrame(sb, fg_color="transparent")
        logo_f.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 4))
        if getattr(self, "_logo_img", None):
            ctk.CTkLabel(logo_f, text="", image=self._logo_img).pack(side="left")
        else:
            ctk.CTkLabel(logo_f, text="✂", font=ctkFont("Segoe UI Symbol", 26), text_color=COLORS.accent_500).pack(side="left")
        name_f = ctk.CTkFrame(logo_f, fg_color="transparent")
        name_f.pack(side="left", padx=8)
        ctk.CTkLabel(name_f, text="SplitForge", font=make_font(TYPO.display_md), text_color=COLORS.text_primary).pack(anchor="w")
        ctk.CTkLabel(name_f, text="Steam Showcase Studio", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w")

        # Theme toggle — compact, always visible
        theme_f = ctk.CTkFrame(sb, fg_color="transparent")
        theme_f.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 8))
        self._theme_btn = AnimButton(
            theme_f, text="🌙  Koyu" if get_theme() == "dark" else "☀️  Açık",
            nc=COLORS.surface_3, hc=COLORS.surface_4, height=28, corner_radius=8,
            font=make_font(TYPO.body_sm), text_color=COLORS.text_muted,
            command=self._toggle_theme,
        )
        self._theme_btn.pack(fill="x")
        # Tooltip hint
        ctk.CTkLabel(theme_f, text="Ctrl+T", font=make_font(TYPO.mono_xs), text_color=COLORS.text_muted).pack()

        # Scrollable body
        body = ctk.CTkScrollableFrame(sb, fg_color="transparent",
            scrollbar_button_color=COLORS.surface_4,
            scrollbar_button_hover_color=COLORS.accent_500)
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        self._section_label(body, "ŞABLON", row=0)

        self._cards_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._cards_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        self._cards = []
        self._rebuild_template_cards()

        # Template management
        AnimButton(body, text="🧩  Şablonlar", nc=COLORS.surface_3, hc=COLORS.surface_4, height=32, corner_radius=8,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_muted,
                   command=lambda: self._open_settings_page("Şablonlar")).grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

        self._sep(body, row=3)

        self._section_label(body, "ARAÇLAR", row=4)

        tools_f = ctk.CTkFrame(body, fg_color="transparent")
        tools_f.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 6))

        AnimButton(tools_f, text="🎮  Steam Çizim Sayfası", nc=COLORS.surface_3, hc=COLORS.surface_4, height=32, corner_radius=8,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_primary, command=self._open_steam_artwork).pack(fill="x", pady=2)

        AnimButton(tools_f, text="📋  Notlar / Console Kodları", nc=COLORS.surface_3, hc=COLORS.surface_4, height=32, corner_radius=8,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_primary,
                   command=lambda: self._open_settings_page("Notlar")).pack(fill="x", pady=2)

        AnimButton(tools_f, text="🎬  GIF / WebP Maker", nc=COLORS.surface_3, hc=COLORS.surface_4, height=32, corner_radius=8,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_primary, command=self._open_gif_maker).pack(fill="x", pady=2)

        AnimButton(tools_f, text="🌐  Community Upload", nc=COLORS.surface_3, hc=COLORS.surface_4, height=32, corner_radius=8,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_primary, command=self._run_steam_community_upload).pack(fill="x", pady=2)

        self._resume_upload_btn = AnimButton(tools_f, text="↻  Upload Devam", nc=COLORS.surface_3, hc=COLORS.surface_4, height=32, corner_radius=8,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_primary, command=self._resume_steam_community_upload)
        if self._has_resumable_upload():
            self._resume_upload_btn.pack(fill="x", pady=2)

        AnimButton(tools_f, text="⚙  Ayarlar", nc=COLORS.surface_3, hc=COLORS.surface_4, height=32, corner_radius=8,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_primary,
                   command=lambda: self._open_settings_page("Genel")).pack(fill="x", pady=2)

        self._sep(body, row=6)

        self._section_label(body, "ÇIKTI KLASÖRÜ", row=7)

        out_f = ctk.CTkFrame(body, fg_color=COLORS.surface_3, corner_radius=RADIUS.lg)
        out_f.grid(row=8, column=0, sticky="ew", padx=8, pady=(0, 16))
        out_f.grid_columnconfigure(0, weight=1)

        self._out_lbl = ctk.CTkLabel(out_f, text=self._short_path(self.output_dir), font=make_font(TYPO.code), text_color=COLORS.text_muted, anchor="w", wraplength=180)
        self._out_lbl.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

        AnimButton(out_f, text="Değiştir", nc=COLORS.surface_3, hc=COLORS.surface_4, height=26, corner_radius=6,
                   font=make_font(TYPO.caption), text_color=COLORS.text_muted, command=self._pick_output_dir).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        self._sync_cards()

    def _sep(self, parent, row):
        ctk.CTkFrame(parent, height=1, fg_color=COLORS.border_hairline).grid(row=row, column=0, sticky="ew", padx=14, pady=4)

    def _section_label(self, parent, text, row):
        ctk.CTkLabel(parent, text=text, font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted
            ).grid(row=row, column=0, sticky="w", padx=18, pady=(6, 2))

    def _short_path(self, p):
        parts = str(p).replace("\\", "/").split("/")
        if len(parts) > 3: return "…/" + "/".join(parts[-2:])
        return str(p)

    def _sync_cards(self):
        for card in self._cards:
            card.set_selected(card.tmpl is self.template or card.tmpl.name == self.template.name)

    def _rebuild_template_cards(self):
        for w in self._cards_frame.winfo_children(): w.destroy()
        self._cards = []
        for t in BUILTIN_TEMPLATES:
            card = TemplateCard(self._cards_frame, t, self._on_template_select)
            card.pack(fill="x", pady=3, padx=2)
            self._cards.append(card)
        self._sync_cards()

    def _on_template_select(self, tmpl):
        self.template = tmpl
        self._sync_cards()
        self._status.set(f"Şablon: {tmpl.name}", COLORS.accent_500, COLORS.accent_500)
        self._status.set_right(tmpl.name)
        if self.current_path and os.path.isfile(self.current_path):
            self._load_preview(self.current_path)

    # ─── Main ───
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        self._main = main
        main.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=16, pady=16)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self._drop = DropZone(main, self._on_file_drop, self._on_batch_drop,
                               initialdir_getter=lambda: self._cfg.get("last_input_dir", ""))
        self._drop.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self._drop.bind_preview_mouse(self._grid_press, self._grid_drag, self._grid_release,
                                       on_double=self._preview_double_click,
                                       on_context=self._preview_context_menu,
                                       on_wheel=self._preview_zoom)
        self._grid_menu = Menu(self, tearoff=0, bg=COLORS.surface_2, fg=COLORS.text_primary,
                                activebackground=COLORS.accent_500, activeforeground=COLORS.surface_0,
                                relief="flat", bd=0)
        for label, where in [("Ortala", "center"), ("Üste Hizala", "top"),
                              ("Alta Hizala", "bottom"), ("Sola Hizala", "left"),
                              ("Sağa Hizala", "right")]:
            self._grid_menu.add_command(label=label, command=lambda w=where: self._grid_snap(w))
        self._grid_menu.add_separator()
        self._grid_menu.add_command(label="🔍 Zoom Sıfırla", command=self._reset_zoom)
        self._grid_menu.add_command(label="🎮 Canlı Vitrin Aç/Kapat", command=self._toggle_live_showcase)
        self._grid_menu.add_command(label="✂ Böl", command=self._split_single)

        self._split_prev = SplitPreview(main, self._back_to_drop, self._open_output_dir,
                                         self._rerun_current, self._clear_outputs,
                                         self._open_file, self._copy_path, self._delete_output_file,
                                         on_upload=self._run_steam_community_upload,
                                         on_selection_change=self._on_split_selection_change)
        self._split_prev.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self._split_prev.grid_remove()

        # Action buttons
        btn_f = ctk.CTkFrame(main, fg_color="transparent")
        btn_f.grid(row=1, column=0, sticky="ew")
        btn_f.grid_columnconfigure((0, 1, 2, 3), weight=1)

        AnimButton(btn_f, text="📂  Dosya Seç", nc=COLORS.surface_3, hc=COLORS.surface_4, height=42, command=self._pick_file
            ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        AnimButton(btn_f, text="📁  Klasör Seç", nc=COLORS.surface_3, hc=COLORS.surface_4, height=42, command=self._pick_folder
            ).grid(row=0, column=1, sticky="ew", padx=5)

        AnimButton(btn_f, text="✂  Böl", nc=COLORS.accent_500, hc=COLORS.accent_600, variant="accent", height=42,
                   text_color=COLORS.surface_0, command=self._split_single).grid(row=0, column=2, sticky="ew", padx=5)

        AnimButton(btn_f, text="⚡  Toplu Böl", nc=COLORS.accent_700, hc=COLORS.accent_500, variant="accent", height=42,
                   text_color=COLORS.text_primary, command=self._split_batch).grid(row=0, column=3, sticky="ew", padx=5)

        # Toolbar
        btn_f2 = ctk.CTkFrame(main, fg_color="transparent")
        btn_f2.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        btn_f2.grid_columnconfigure(2, weight=1)

        self._fx_btn = AnimButton(btn_f2, text="🎨  Efektler", nc=COLORS.surface_3, hc=COLORS.info_500, height=36,
                   font=make_font(TYPO.body_md), command=self._toggle_effects_panel)
        self._fx_btn.grid(row=0, column=0, padx=(0, 8))

        self._suggest_btn = AnimButton(btn_f2, text="🤖  Şablon Öner", nc=COLORS.surface_3, hc=COLORS.success, height=36,
                   font=make_font(TYPO.body_md), command=self._toggle_suggestions_panel)
        self._suggest_btn.grid(row=0, column=1, padx=(0, 8))

        AnimButton(btn_f2, text="🎮  Canlı Vitrin", height=36, nc=COLORS.surface_3, hc=COLORS.info_500,
                   font=make_font(TYPO.body_md), command=self._toggle_live_showcase).grid(row=0, column=2)

        ctk.CTkLabel(btn_f2, text="Bant sayısı", font=make_font(TYPO.body_md), text_color=COLORS.text_muted
            ).grid(row=0, column=3, padx=(2, 6))

        self._band_entry = ctk.CTkEntry(btn_f2, fg_color=COLORS.surface_3, border_color=COLORS.border_default,
                                         text_color=COLORS.text_primary, height=36, width=48, justify="center")
        self._band_entry.insert(0, str(self._cfg.get("multi_band_count", 3)))
        self._band_entry.grid(row=0, column=4)
        self._band_entry.bind("<KeyRelease>", lambda _e: (
            self._load_preview(self.current_path)
            if self.current_path and os.path.isfile(self.current_path) else None))

        # Status bar
        self._status = StatusBar(main)
        self._status.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self._status.set_right(self.template.name)

    # ─── Events ───
    def _remember_input_dir(self, d):
        if d and os.path.isdir(d):
            self._cfg["last_input_dir"] = d
            get_config_service().save_config()

    def _on_file_drop(self, path):
        self._batch_files = None
        self._grid_pos = None
        self._grid_scale = 1.0
        if os.path.isdir(path):
            self.current_path = path
            self._drop.reset()
            self._remember_input_dir(path)
            self._status.set(f"Klasör: {os.path.basename(path)}", COLORS.text_primary, COLORS.success)
            return
        self.current_path = path
        self._remember_input_dir(os.path.dirname(path))
        self._load_preview(path)
        self._status.set(f"Yüklendi: {os.path.basename(path)}", COLORS.text_primary, COLORS.success)

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
        self._status.set(f"{len(valid)} dosya seçildi (toplu bölme)", COLORS.text_primary, COLORS.success)

    def _on_split_selection_change(self, indices: list[int]):
        if indices:
            self._status.set(f"{len(indices)} parça seçili", COLORS.text_primary, COLORS.info)
        else:
            self._status.set("", COLORS.text_muted, None)

    def _current_band_count(self) -> int:
        try:
            return max(1, int(self._band_entry.get().strip()))
        except Exception:
            return 1

    def _toggle_live_showcase(self):
        """Toggle live showcase PIP overlay on preview."""
        self._live_showcase = not getattr(self, "_live_showcase", False)
        if self.current_path and os.path.isfile(self.current_path):
            self._load_preview(self.current_path)
        status = "açık" if self._live_showcase else "kapalı"
        self._status.set(f"Canlı vitrin: {status}", COLORS.text_primary, COLORS.info if self._live_showcase else COLORS.text_muted)

    def _toggle_theme(self):
        """Dark/Light toggle — persists, requires restart for full refresh."""
        try:
            new = toggle_theme()
            self._cfg["theme"] = new
            get_config_service().save_config()
            # Update button label
            if hasattr(self, "_theme_btn"):
                self._theme_btn.configure(text="☀️  Açık" if new == "light" else "🌙  Koyu")
            self._status.set(
                f"Tema: {'Açık' if new == 'light' else 'Koyu'} — yeniden başlatın (tam efekt için)",
                COLORS.text_primary, COLORS.info,
            )
        except Exception as e:
            from steameditor.services.log_service import get_logger
            get_logger("theme").error(f"Theme toggle failed: {e}")

    def _toggle_suggestions_panel(self):
        """Toggle AI template suggestions panel."""
        if getattr(self, "_suggestions_open", False):
            if getattr(self, "_suggestions_panel", None):
                self._suggestions_panel.place_forget()
            self._suggestions_open = False
            return
        
        self._build_suggestions_panel()
        # Position on the right side of the drop zone
        self._suggestions_panel.place(x=10, y=10, relheight=0.96, width=320)
        self._suggestions_panel.lift()
        self._suggestions_open = True

    def _build_suggestions_panel(self):
        """Build the AI template suggestions panel."""
        if getattr(self, "_suggestions_panel", None):
            self._suggestions_panel.destroy()
        
        panel = ctk.CTkFrame(self._drop, fg_color=COLORS.surface_1, corner_radius=12,
            scrollbar_button_color=COLORS.surface_4, scrollbar_button_hover_color=COLORS.accent_500)
        self._suggestions_panel = panel
        
        # Header
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(hdr, text="🤖  Şablon Önerileri", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(side="left", padx=4)
        AnimButton(hdr, text="✕", width=30, height=26, nc=COLORS.surface_3, hc=COLORS.surface_4,
                   text_color=COLORS.text_muted, command=lambda: panel.place_forget()).pack(side="right", padx=2)

        # Suggestions content
        self._suggestions_content = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self._suggestions_content.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        
        # Initial placeholder
        self._suggestions_placeholder = ctk.CTkLabel(self._suggestions_content, 
            text="Görsel yüklendiğinde AI önerileri burada görünecek",
            font=make_font(TYPO.body_md), text_color=COLORS.text_muted, justify="center")
        self._suggestions_placeholder.pack(pady=40)
        
        # Update suggestions if we have a current image
        if self.current_path and os.path.isfile(self.current_path):
            self._update_suggestions(self.current_path)
        
        # Refresh button
        btn_frame = ctk.CTkFrame(panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=6, pady=(0, 8))
        AnimButton(btn_frame, text="🔄 Yenile", variant="accent", height=32, text_color=COLORS.surface_0,
                   command=lambda: self._update_suggestions(self.current_path)).pack(fill="x")

    def _update_suggestions(self, path):
        """Update suggestions panel with AI recommendations for the given image."""
        if not getattr(self, "_suggestions_panel", None) or not self._suggestions_open:
            return
            
        try:
            img = Image.open(path)
            if hasattr(img, "n_frames") and img.n_frames > 1:
                img.seek(0)
            img = img.convert("RGBA")
            
            # Clear old content
            for w in self._suggestions_content.winfo_children():
                w.destroy()
            self._suggestions_placeholder.pack_forget()
            
            # Get recommendations
            from steameditor.core.template_matcher import get_template_matcher
            matcher = get_template_matcher()
            matches = matcher.recommend(img, top_k=5)
            
            if not matches:
                ctk.CTkLabel(self._suggestions_content, text="Uygun şablon bulunamadı",
                    font=make_font(TYPO.body_md), text_color=COLORS.text_muted).pack(pady=20)
                return
            
            # Steam showcase type recommendation
            showcase_rec = matcher.get_steam_showcase_recommendation(img)
            if showcase_rec:
                showcase_frame = ctk.CTkFrame(self._suggestions_content, fg_color=COLORS.accent_subtle, corner_radius=8)
                showcase_frame.pack(fill="x", pady=(0, 12), padx=4)
                ctk.CTkLabel(showcase_frame, text="🎮 Steam Vitrin Türü", font=make_font(TYPO.caption, weight="bold"),
                    text_color=COLORS.accent_500).pack(anchor="w", padx=10, pady=(8, 2))
                ctk.CTkLabel(showcase_frame, text=showcase_rec["description"], font=make_font(TYPO.body_sm),
                    text_color=COLORS.text_primary).pack(anchor="w", padx=10, pady=(0, 2))
                ctk.CTkLabel(showcase_frame, text=f"Güven: {showcase_rec['confidence'].capitalize()}",
                    font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=10, pady=(0, 8))
            
            # Template matches
            for match in matches:
                self._create_suggestion_card(match)
                
        except Exception as e:
            ctk.CTkLabel(self._suggestions_content, text=f"Öneri hesaplanamadı: {e}",
                font=make_font(TYPO.body_sm), text_color=COLORS.error).pack(pady=20)

    def _create_suggestion_card(self, match):
        """Create a card for a template match."""
        card = ctk.CTkFrame(self._suggestions_content, fg_color=COLORS.surface_2, corner_radius=10, border_width=1,
                           border_color=COLORS.border_default)
        card.pack(fill="x", pady=4, padx=4)
        
        # Confidence badge
        conf_colors = {"high": COLORS.success, "medium": COLORS.warning, "low": COLORS.text_muted}
        conf_text = {"high": "🟢 Yüksek", "medium": "🟡 Orta", "low": "🔴 Düşük"}
        badge = ctk.CTkLabel(card, text=conf_text.get(match.confidence, match.confidence),
                             font=make_font(TYPO.caption, weight="bold"), text_color=conf_colors.get(match.confidence, COLORS.text_primary),
                             fg_color=COLORS.accent_subtle, corner_radius=4, padx=8, pady=2)
        badge.grid(row=0, column=0, rowspan=2, padx=(10, 8), pady=10, sticky="n")

        # Template info
        tmpl = match.template
        icons = {"uniform": "⚡", "multi": "✏️", "single": "🖼"}
        icon = icons.get(tmpl.mode, "◆")
        
        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont("Segoe UI Emoji", 20), text_color=COLORS.accent_500).grid(row=0, column=1, sticky="w", pady=(8, 0))
        ctk.CTkLabel(card, text=tmpl.name, font=make_font(TYPO.heading_sm), text_color=COLORS.text_primary, wraplength=200).grid(row=1, column=1, sticky="w", padx=(8, 10))

        # Score + top reasons
        score_pct = int(match.score * 100)
        reasons_text = " · ".join(match.reasons[:2]) if match.reasons else "Genel uyum"
        ctk.CTkLabel(card, text=f"Uyum: %{score_pct}  —  {reasons_text}",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted, wraplength=200).grid(row=2, column=1, sticky="w", padx=(8, 10), pady=(0, 4))

        # Dimensions
        if tmpl.mode == "uniform":
            parts = tmpl.parts if isinstance(tmpl.parts, int) else 5
            dim_text = f"⚡ {tmpl.width}×{tmpl.height}px  ·  {parts} parça"
        elif tmpl.mode == "multi":
            parts = tmpl.parts if isinstance(tmpl.parts, list) else []
            total_w = sum(p.width for p in parts)
            dim_text = f"✏️ {len(parts)} parça  ·  Toplam {total_w}×{tmpl.height}px"
        else:
            dim_text = f"🖼 {tmpl.width}×{tmpl.height}px  ·  Tek parça"
        ctk.CTkLabel(card, text=dim_text, font=make_font(TYPO.caption), text_color=COLORS.text_muted).grid(row=3, column=1, sticky="w", padx=(8, 10), pady=(0, 8))

        # Actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=4, padx=10, pady=8, sticky="ns")

        AnimButton(actions, text="Seç", variant="accent", height=28, text_color=COLORS.surface_0,
                   command=lambda m=match: self._on_template_select(m.template)).pack(pady=2)
        AnimButton(actions, text="Uygula", nc=COLORS.surface_3, hc=COLORS.surface_4, height=26, corner_radius=6,
                   font=make_font(TYPO.body_sm), text_color=COLORS.text_primary,
                   command=lambda m=match: self._apply_template_suggestion(m.template)).pack(pady=2)

    def _apply_template_suggestion(self, template):
        """Apply a template suggestion and update UI."""
        self.template = template
        self._sync_cards()
        self._status.set(f"Şablon uygulandı: {template.name}", COLORS.accent_500, COLORS.accent_500)
        self._status.set_right(template.name)
        if self.current_path and os.path.isfile(self.current_path):
            self._load_preview(self.current_path)
        if self._suggestions_open:
            self._suggestions_panel.place_forget()
            self._suggestions_open = False

    def _load_preview(self, path):
        try:
            img = Image.open(path)
            if hasattr(img, "n_frames") and img.n_frames > 1:
                img.seek(0)
            img = autocrop_borders(img.convert("RGBA"), self._cfg)
            tmpl = self.template
            if (tmpl.mode == "uniform"
                    and img.width >= tmpl.width * 0.75
                    and img.height >= tmpl.height * 0.75):
                self._setup_interactive_preview(img)
                return
            self._pv = None
            self._grid_pos = None
            bands = self._current_band_count()
            preview = render_template_preview(img, tmpl, self._cfg, band_count=bands)
            summary = template_output_summary(img, tmpl, band_count=bands)
            if (tmpl.mode == "uniform"
                    and (img.width < tmpl.width or img.height < tmpl.height)):
                summary += (f" · ⚠ kaynak ({img.width}×{img.height}) şablondan küçük,"
                            f" büyütülerek kesilecek (kalite kaybı)")
            batch_count = len(self._batch_files) if self._batch_files else 0
            self._drop.show_image(preview, summary, batch_count=batch_count)
        except Exception as e:
            self._status.error(f"Önizleme hatası: {e}")

    # ─── Interactive Preview ───
    def _setup_interactive_preview(self, img):
        tmpl = self.template
        tw_total, th = tmpl.width, tmpl.height
        parts = tmpl.parts if isinstance(tmpl.parts, int) else 5
        img = _apply_effects_pipeline(img, {**self._cfg, "text_overlay_enabled": False})
        W, H = img.size

        gscale = max(0.3, min(self._grid_scale, W / tw_total, H / th))
        bands_fit = max(1, min(self._current_band_count(), int(H // (th * gscale))))

        disp_w = max(self._drop.winfo_width(), 700) - 24
        disp_h = max(self._drop.winfo_height(), 480) - 24
        disp = img.convert("RGB")
        disp.thumbnail((max(1, disp_w), max(1, disp_h)), Image.LANCZOS)

        self._grid_scale = gscale
        prev = self._pv
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
        pv = self._pv
        dw, dh = pv["disp"].size
        z = pv.get("zoom", 1.0)
        cw, ch = dw / z, dh / z
        fx, fy = pv.get("focus", (0.5, 0.5))
        x0 = max(0.0, min(dw - cw, fx * dw - cw / 2))
        y0 = max(0.0, min(dh - ch, fy * dh - ch / 2))
        return x0, y0, cw, ch

    def _disp_from_event(self, e):
        pv = self._pv
        z = pv.get("zoom", 1.0)
        if z <= 1.0: return e.x, e.y
        x0, y0, _cw, _ch = self._view_crop()
        return x0 + e.x / z, y0 + e.y / z

    def _suggest_matching_template(self, W, H, gscale):
        if gscale >= 0.95: return
        best = None
        for t2 in BUILTIN_TEMPLATES:
            if t2 is self.template or t2.mode != "uniform": continue
            if W >= t2.width and H >= t2.height:
                coverage = (t2.width * t2.height) / (W * H)
                if best is None or coverage > best[1]:
                    best = (t2, coverage)
        if best:
            name = best[0].name
            self.after(250, lambda: self._status.set(
                f"💡 Bu kaynağa ({W}×{H}) birebir uyan şablon: {name} — sol menüden seç",
                COLORS.accent_400, COLORS.accent_400, auto_reset=False))

    def _show_onboarding_tip(self):
        if self._cfg.get("onboarding_tips_shown"): return
        self._cfg["onboarding_tips_shown"] = True
        get_config_service().save_config()
        tip = ctk.CTkLabel(self._drop,
            text="  💡 Grid'i fareyle sürükle · köşesinden boyutlandır · sağ tık: hizalama menüsü  ",
            font=make_font(TYPO.body_sm, weight="bold"), text_color=COLORS.surface_0, fg_color=COLORS.accent_500, corner_radius=10, padx=10, pady=6)
        tip.place(relx=0.5, y=16, anchor="n")
        self.after(9000, lambda: tip.winfo_exists() and tip.destroy())

    def _apply_grid_geometry(self):
        pv = self._pv
        W, H = pv["img_size"]
        gscale = self._grid_scale
        gw = int(round(pv["tw_total"] * gscale))
        gh = int(round(pv["band_h"] * pv["bands"] * gscale))
        pv["grid"] = (gw, gh)
        if self._grid_pos is None:
            gx, gy = (W - gw) // 2, max(0, (H - gh) // 2)
        else:
            gx, gy = self._grid_pos
        self._grid_pos = (max(0, min(W - gw, int(gx))), max(0, min(H - gh, int(gy))))

    def _draw_grid_overlay(self):
        pv = self._pv
        if not pv: return
        base = pv["disp"].copy()
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
        bounds = uniform_slice_bounds(pv["tw_total"], parts)
        for b in range(pv["bands"]):
            y1 = gy + b * th_g
            for i, (bx1, bx2) in enumerate(bounds):
                x1 = gx + bx1 * gscale
                x2 = gx + bx2 * gscale
                fill = (249, 115, 22, 26) if (b * parts + i) % 2 == 0 else (99, 102, 241, 22)
                d.rectangle((x1 * s, y1 * s, x2 * s, (y1 + th_g) * s), fill=fill, outline=(249, 115, 22, 255), width=2)
        cx, cy = (gx + gw) * s, (gy + gh) * s
        d.rectangle((cx - 7, cy - 7, cx + 7, cy + 7), fill=(249, 115, 22, 255), outline=(8, 8, 8, 255), width=2)

        if self._live_showcase:
            pip = self._compose_pip_showcase(base)
            px = base.width - pip.width - 10
            py = base.height - pip.height - 10
            base.paste(pip, (px, py))
            d.rectangle((px - 1, py - 1, px + pip.width, py + pip.height), outline=(249, 115, 22, 255), width=1)

        W, H = pv["img_size"]
        patch = " · patch açık" if self.template.patch else ""
        th_total = th * pv["bands"]
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
        z = pv.get("zoom", 1.0)
        if z > 1.0:
            x0, y0, cw, ch = self._view_crop()
            crop = base.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))
            base = crop.resize(pv["disp"].size, Image.LANCZOS)
            info += f" · 🔍 %{round(z * 100)} (tekerlek: zoom, sağ tık: sıfırla)"
        batch_count = len(self._batch_files) if self._batch_files else 0
        self._drop.show_image(base, info, batch_count=batch_count)

    def _compose_pip_showcase(self, base):
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
        pip.thumbnail((max(60, base.width // 3), max(60, int(base.height * 0.55))), Image.BILINEAR)
        return pip

    # ─── Event Handlers ───
    def _grid_press(self, e):
        pv = self._pv
        if not pv: return
        s = pv["scale"]
        dx, dy = self._disp_from_event(e)
        gx, gy = self._grid_pos
        gw, gh = pv["grid"]
        tb = pv.get("text_bbox")
        if tb and tb[0] - 4 <= dx <= tb[2] + 4 and tb[1] - 4 <= dy <= tb[3] + 4:
            disp = pv["disp"]
            tw_txt, th_txt = tb[2] - tb[0], tb[3] - tb[1]
            denom_x = max(1, disp.width - tw_txt)
            denom_y = max(1, disp.height - th_txt)
            pv["press"] = ("text", dx, dy, tb[0] / denom_x, tb[1] / denom_y, denom_x, denom_y)
            return
        cx, cy = (gx + gw) * s, (gy + gh) * s
        if abs(dx - cx) <= 12 and abs(dy - cy) <= 12:
            pv["press"] = ("resize", dx, dy, self._grid_scale, max(1.0, gw * s))
        else:
            pv["press"] = ("move", dx, dy, gx, gy)

    def _preview_double_click(self, _e=None):
        if self._pv: self._split_single()

    def _preview_context_menu(self, e):
        if self._pv:
            try: self._grid_menu.tk_popup(e.x_root, e.y_root)
            finally: self._grid_menu.grab_release()

    def _preview_zoom(self, e):
        pv = self._pv
        if not pv: return
        z0 = pv.get("zoom", 1.0)
        z = z0 * (1.15 if e.delta > 0 else 1 / 1.15)
        z = max(1.0, min(5.0, z))
        if abs(z - z0) < 0.001: return
        dw, dh = pv["disp"].size
        dx, dy = self._disp_from_event(e)
        pv["focus"] = (dx / dw, dy / dh)
        pv["zoom"] = z
        if z <= 1.0: pv["focus"] = (0.5, 0.5)
        self._draw_grid_overlay()
