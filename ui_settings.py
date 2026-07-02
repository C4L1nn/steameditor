"""ui_settings.py — tek pencere içi Ayarlar sayfası (SettingsPage).

Genel/Efektler/Şablonlar/Profiller/Projeler/Steam API/Notlar sekmelerinin
tamamı; App'e self.app üzerinden bağlanır, hiç yeni OS penceresi açmaz.
"""
import os
import webbrowser

import customtkinter as ctk
from tkinter import Text, BooleanVar, StringVar, messagebox, colorchooser

from ui_theme import (
    C_ACCENT, C_ACC_LT, C_BG0, C_BG1, C_BG2, C_BG3, C_BG4, C_BG5,
    C_BORDER, C_DIM, C_ERROR, C_SUCCESS, C_TEXT,
    AnimButton,
)
from core import _TEXT_OVERLAY_POSITIONS, list_border_templates
from config import (
    PROFILE_KEYS,
    STEAM_CONSOLE_SNIPPETS,
    STEAM_DIRECT_UPLOAD_NOTE,
    STEAM_HELPER_LINKS,
    STEAM_UPLOAD_STEPS,
    TEMPLATES,
    TEMPLATE_SNIPPET_HINTS,
    _masked_key,
    fetch_steam_published_file_details,
    load_profiles,
    load_projects,
    save_config,
    save_custom_presets,
    save_profiles,
    save_projects,
    steam_api_config_errors,
)


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

        ctk.CTkLabel(p, text="ÇIKTI",
                     font=ctk.CTkFont("Segoe UI", 9, weight="bold"),
                     text_color=C_DIM).pack(anchor="w", padx=4, pady=(14, 4))

        fmt_row = ctk.CTkFrame(p, fg_color="transparent")
        fmt_row.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkLabel(fmt_row, text="Görsel formatı",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C_DIM).pack(side="left")
        fmt_var = StringVar(value="JPG" if cfg.get("output_format") == "jpg" else "PNG")
        ctk.CTkOptionMenu(
            fmt_row, values=["PNG", "JPG"], variable=fmt_var, width=110,
            fg_color=C_BG3, button_color=C_ACCENT, button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3, dropdown_hover_color=C_BG4,
            text_color=C_TEXT).pack(side="right")
        ctk.CTkLabel(p, text="Not: Workshop son-byte patch hilesi sadece PNG'de uygulanır; "
                             "JPG daha küçük dosya üretir ama patch atlanır.",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=C_DIM,
                     wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 4))
        jpg_quality_slider = self._slider_row(p, "JPG kalitesi", cfg, "jpg_quality", 90,
                                              from_=40, to=100, fmt="{}")
        gif_lossy_slider = self._slider_row(p, "GIF sıkıştırma gücü (lossy)", cfg, "gif_lossy", 80,
                                            from_=0, to=200, fmt="{}")
        gif_colors_slider = self._slider_row(p, "GIF renk sayısı", cfg, "gif_colors", 128,
                                             from_=16, to=256, fmt="{}")

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
            cfg["output_format"] = "jpg" if fmt_var.get() == "JPG" else "png"
            cfg["jpg_quality"] = int(jpg_quality_slider.get())
            cfg["gif_lossy"] = int(gif_lossy_slider.get())
            cfg["gif_colors"] = int(gif_colors_slider.get())
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

        # Tip seçici: Uniform (eşit parçalar) / Multi (farklı boyutlar) / Single
        mode_var = StringVar(value="Uniform (eşit parçalar)")
        mode_map = {"Uniform (eşit parçalar)": "uniform",
                    "Multi (farklı boyutlu parçalar)": "multi",
                    "Single (tek parça)": "single"}
        ctk.CTkOptionMenu(
            new_card, values=list(mode_map), variable=mode_var,
            fg_color=C_BG4, button_color=C_ACCENT, button_hover_color=C_ACC_LT,
            dropdown_fg_color=C_BG3, dropdown_hover_color=C_BG4,
            text_color=C_TEXT, command=lambda _v: sync_mode_fields()
        ).pack(fill="x", padx=10, pady=(0, 6))

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

        # Multi mod: "506x800, 100x800" formatında parça listesi
        multi_frame = ctk.CTkFrame(new_card, fg_color="transparent")
        ctk.CTkLabel(multi_frame, text="Parçalar — GENİŞLIKxYÜKSEKLİK, virgülle (ör. 506x800, 100x800)",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C_DIM).pack(anchor="w")
        multi_entry = ctk.CTkEntry(multi_frame, fg_color=C_BG4, border_color=C_BORDER,
                                   text_color=C_TEXT, height=30,
                                   placeholder_text="506x800, 100x800")
        multi_entry.pack(fill="x", pady=(2, 0))

        def sync_mode_fields():
            mode = mode_map[mode_var.get()]
            if mode == "multi":
                row.pack_forget()
                if not multi_frame.winfo_manager():
                    multi_frame.pack(fill="x", padx=10, pady=(0, 4), before=add_btn)
            else:
                multi_frame.pack_forget()
                if not row.winfo_manager():
                    row.pack(fill="x", padx=10, pady=(0, 4), before=add_btn)
                # single'da parça sayısı alanı anlamsız
                new_fields["n"].configure(state="disabled" if mode == "single" else "normal")

        def parse_multi_parts(text):
            parts = []
            for chunk in text.split(","):
                chunk = chunk.strip().lower().replace("×", "x")
                if not chunk:
                    continue
                w_str, _, h_str = chunk.partition("x")
                parts.append({"width": int(w_str), "height": int(h_str)})
            return parts

        def create_template():
            mode = mode_map[mode_var.get()]
            try:
                if mode == "multi":
                    parts = parse_multi_parts(multi_entry.get())
                    if not parts or any(p["width"] <= 0 or p["height"] <= 0 for p in parts):
                        raise ValueError
                    widths = "+".join(str(p["width"]) for p in parts)
                    tmpl = {"name": f"Özel Multi ({widths})", "mode": "multi",
                            "parts": parts, "patch": False, "prefix": "cus"}
                else:
                    pw = int(new_fields["w"].get())
                    ph = int(new_fields["h"].get())
                    if pw <= 0 or ph <= 0:
                        raise ValueError
                    if mode == "single":
                        tmpl = {"name": f"Özel Tek ({pw}×{ph})", "mode": "single",
                                "width": pw, "height": ph, "patch": False, "prefix": "cus"}
                    else:
                        cnt = int(new_fields["n"].get())
                        if cnt <= 0:
                            raise ValueError
                        tmpl = {"name": f"Özel ({pw}×{ph} ×{cnt})", "mode": "uniform",
                                "width": pw * cnt, "height": ph, "parts": cnt,
                                "patch": False, "prefix": "cus"}
            except ValueError:
                self.app._status.error("Geçerli değerler gir (multi için: 506x800, 100x800 gibi)")
                return
            if any(t["name"] == tmpl["name"] for t in TEMPLATES):
                self.app._status.error("Aynı isimde şablon zaten var")
                return
            TEMPLATES.append(tmpl)
            self.app.template = tmpl
            save_custom_presets()
            self.app._rebuild_template_cards()
            self.app._status.set(f"Şablon eklendi: {tmpl['name']}", C_SUCCESS, C_SUCCESS)
            self.open_tab("Şablonlar")

        add_btn = AnimButton(new_card, text="＋  Ekle",
                             variant="accent", height=32, text_color=C_BG0,
                             command=create_template)
        add_btn.pack(fill="x", padx=10, pady=(6, 10))

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
            mode = t.get("mode", "uniform")
            is_uniform = mode == "uniform"
            # uniform ve single alan bazında düzenlenebilir; multi'nin parça
            # listesi bu forma sığmaz — sil + yeniden oluştur.
            editable = (t.get("prefix") not in ("work", "art", "shot")
                        and mode in ("uniform", "single"))
            for key, entry in fields.items():
                entry.configure(state="normal")
                entry.delete(0, "end")
            fields["name"].insert(0, t.get("name", ""))
            fields["width"].insert(0, str(t.get("width", "")))
            fields["height"].insert(0, str(t.get("height", "")))
            fields["parts"].insert(0, str(t.get("parts", "")) if is_uniform else "")
            fields["prefix"].insert(0, t.get("prefix", ""))
            patch_var.set(bool(t.get("patch", False)))
            state = "normal" if editable else "disabled"
            for key, entry in fields.items():
                entry.configure(state="disabled" if (key == "parts" and not is_uniform) else state)

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
            mode = (t or {}).get("mode", "uniform")
            if not t or t.get("prefix") in ("work", "art", "shot"):
                self.app._status.error("Yerleşik şablonlar düzenlenemez")
                return
            if mode == "multi":
                self.app._status.error("Multi şablonu düzenlemek için silip yeniden oluştur")
                return
            try:
                name = fields["name"].get().strip()
                width = int(fields["width"].get())
                height = int(fields["height"].get())
                parts = int(fields["parts"].get()) if mode == "uniform" else 0
                prefix = fields["prefix"].get().strip() or "cus"
                if not name or width <= 0 or height <= 0 or (mode == "uniform" and parts <= 0):
                    raise ValueError
            except ValueError:
                self.app._status.error("Şablon değerleri geçersiz")
                return
            updates = {"name": name, "width": width, "height": height,
                       "patch": bool(patch_var.get()), "prefix": prefix}
            if mode == "uniform":
                updates["parts"] = parts
            t.update(updates)
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
            # O anki efekt/upload ayarlarını da projeye dondur — kuyruk ya da
            # "Aç" ile geri dönünce proje, kaydedildiği andaki efektlerle
            # (border/metin/iyileştir) bölünür, o ANKİ global ayarlarla değil.
            entry["effects"] = {k: app._cfg.get(k) for k in PROFILE_KEYS}
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
            # Projeyle birlikte dondurulmuş efekt ayarlarını da geri yükle
            effects = data.get("effects")
            if isinstance(effects, dict):
                for k in PROFILE_KEYS:
                    if k in effects and effects[k] is not None:
                        app._cfg[k] = effects[k]
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
