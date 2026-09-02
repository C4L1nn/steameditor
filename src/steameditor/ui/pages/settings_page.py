"""steameditor.ui.pages.settings_page — Unified settings page."""

from __future__ import annotations

import os
import time
import webbrowser
from pathlib import Path
from tkinter import Text, BooleanVar, StringVar, messagebox, colorchooser
from typing import Any, Callable

import customtkinter as ctk

from steameditor.core.models import (
    Template, EffectConfig, BUILTIN_TEMPLATES,
)
from steameditor.config import (
    STEAM_CONSOLE_SNIPPETS, STEAM_HELPER_LINKS, STEAM_UPLOAD_STEPS,
    TEMPLATE_SNIPPET_HINTS, clear_history, load_history,
    load_profiles, load_projects, save_custom_presets,
    save_profiles, save_projects,
)
from steameditor.services import get_config_service
from steameditor.services.flat_config import FlatConfig
from steameditor.ui.components import AnimButton
from steameditor.ui.design_system import (
    COLORS, TYPO, make_font, apply_theme,
)
from steameditor.ui.pages.template_manager import TemplateManagerPage


class SettingsPage(ctk.CTkFrame):
    """Unified settings page with tabs."""

    TABS = [
        ("Genel", "⚙"),
        ("Şablonlar", "🧩"),
        ("Şablon Yönetimi", "🛠"),
        ("Profiller", "🗂"),
        ("Projeler", "📁"),
        ("Geçmiş", "🕘"),
        ("Notlar", "📋"),
    ]

    def __init__(self, master, app, on_back, **kw):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=COLORS.bg_2, border_color=COLORS.border_default, **kw)
        self.app = app
        self._on_back = on_back
        self._current_tab = None
        self._nav_buttons = {}
        self._notes_txt = None
        self._notes_path = Path(__file__).parent.parent.parent.parent / "steam_notes.txt"

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS.bg_3, corner_radius=0, height=44)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="⚙  Ayarlar", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(side="left", padx=14)
        AnimButton(hdr, text="← Geri", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_muted, command=self._back).pack(side="right", padx=10, pady=8)

        # Nav
        nav = ctk.CTkFrame(self, fg_color=COLORS.bg_1, width=152, corner_radius=0)
        nav.grid(row=1, column=0, sticky="nsw")
        nav.grid_propagate(False)
        for name, icon in self.TABS:
            btn = ctk.CTkButton(nav, text=f"{icon}  {name}", anchor="w", height=38, corner_radius=8,
                                font=make_font(TYPO.body_md, weight="bold"), fg_color="transparent",
                                hover_color=COLORS.bg_3, text_color=COLORS.text_muted,
                                command=lambda n=name: self.open_tab(n))
            btn.pack(fill="x", padx=8, pady=3)
            self._nav_buttons[name] = btn

        # Content
        self._content = ctk.CTkScrollableFrame(self, fg_color="transparent",
            scrollbar_button_color=COLORS.bg_4, scrollbar_button_hover_color=COLORS.accent)
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
            btn.configure(fg_color=COLORS.bg_3 if active else "transparent",
                         text_color=COLORS.accent if active else COLORS.text_muted)
        for w in self._content.winfo_children():
            w.destroy()
        builder = {
            "Genel": self._build_general,
            "Şablonlar": self._build_templates,
            "Şablon Yönetimi": self._build_template_manager,
            "Profiller": self._build_profiles,
            "Projeler": self._build_projects,
            "Geçmiş": self._build_history,
            "Notlar": self._build_notes,
        }[name]
        builder(self._content)

    # ═══════════════════════════════════════════════════════════════════
    # Genel
    # ═══════════════════════════════════════════════════════════════════
    def _build_general(self, p):
        cfg = FlatConfig(get_config_service().config)
        ctk.CTkLabel(p, text="Genel Ayarlar", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", padx=4, pady=(4, 12))

        open_var = BooleanVar(value=bool(cfg.get("open_output_after_process", False)))
        ctk.CTkCheckBox(p, text="İşlem bitince çıktı klasörünü otomatik aç", variable=open_var,
                        font=make_font(TYPO.body_md), text_color=COLORS.text_primary,
                        fg_color=COLORS.accent, hover_color=COLORS.accent_hover, checkmark_color=COLORS.bg_0).pack(anchor="w", padx=4, pady=8)

        upload_var = BooleanVar(value=bool(cfg.get("auto_upload", False)))
        ctk.CTkCheckBox(p, text="Split sonrası Steam Community upload otomasyonunu aç", variable=upload_var,
                        font=make_font(TYPO.body_md), text_color=COLORS.text_primary,
                        fg_color=COLORS.accent, hover_color=COLORS.accent_hover, checkmark_color=COLORS.bg_0).pack(anchor="w", padx=4, pady=8)

        community_submit_var = BooleanVar(value=bool(cfg.get("steam_community_auto_submit", False)))
        ctk.CTkCheckBox(p, text="Community upload sırasında submit butonunu otomatik dene", variable=community_submit_var,
                        font=make_font(TYPO.body_md), text_color=COLORS.text_primary,
                        fg_color=COLORS.accent, hover_color=COLORS.accent_hover, checkmark_color=COLORS.bg_0).pack(anchor="w", padx=4, pady=8)

        ctk.CTkLabel(p, text="ÇIKTI", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=(14, 4))

        fmt_row = ctk.CTkFrame(p, fg_color="transparent")
        fmt_row.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkLabel(fmt_row, text="Görsel formatı", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(side="left")
        fmt_var = StringVar(value="JPG" if cfg.get("output_format") == "jpg" else "PNG")
        ctk.CTkOptionMenu(fmt_row, values=["PNG", "JPG"], variable=fmt_var, width=110,
                          fg_color=COLORS.bg_3, button_color=COLORS.accent, button_hover_color=COLORS.accent_hover,
                          dropdown_fg_color=COLORS.bg_3, dropdown_hover_color=COLORS.bg_4,
                          text_color=COLORS.text_primary).pack(side="right")
        ctk.CTkLabel(p, text="Not: Workshop son-byte patch hilesi sadece PNG'de uygulanır; JPG daha küçük dosya üretir ama patch atlanır.",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted, wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 4))

        def slider_row(label, key, default, from_=0, to=100, fmt="{}"):
            frame = ctk.CTkFrame(p, fg_color="transparent")
            frame.pack(fill="x", padx=4, pady=6)
            top = ctk.CTkFrame(frame, fg_color="transparent"); top.pack(fill="x")
            ctk.CTkLabel(top, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(side="left")
            value_lbl = ctk.CTkLabel(top, text="", font=make_font(TYPO.code, weight="bold"), text_color=COLORS.accent)
            value_lbl.pack(side="right")
            slider = ctk.CTkSlider(frame, from_=from_, to=to, button_color=COLORS.accent,
                                   button_hover_color=COLORS.accent_hover, progress_color=COLORS.accent, fg_color=COLORS.bg_4)
            slider.pack(fill="x", pady=(4, 0))
            raw = cfg.get(key, default)
            slider.set(int(raw) if raw is not None else default)
            def update(value):
                value_lbl.configure(text=fmt.format(int(float(value))))
                cfg[key] = int(float(value))
            slider.configure(command=update)
            update(slider.get())
            return slider

        slider_row("JPG kalitesi", "jpg_quality", 90, from_=40, to=100, fmt="{}")
        slider_row("GIF sıkıştırma gücü (lossy)", "gif_lossy", 30, from_=0, to=200, fmt="{}")
        slider_row("GIF renk sayısı", "gif_colors", 256, from_=16, to=256, fmt="{}")

        ctk.CTkLabel(p, text="STEAM COMMUNITY OTOMASYONU", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=(14, 4))

        community_entries = {}
        for label, key in [
            ("Upload URL", "steam_community_upload_url"),
            ("Tarayıcı profil klasörü", "steam_community_profile_dir"),
            ("Upload başlığı", "steam_community_title_template"),
            ("Dosya seçtikten sonra bekleme (ms)", "steam_community_wait_after_upload_ms"),
        ]:
            ctk.CTkLabel(p, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(p, fg_color=COLORS.bg_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=30)
            e.insert(0, str(cfg.get(key, "")))
            e.pack(fill="x", padx=4, pady=(2, 7))
            community_entries[key] = e

        ctk.CTkLabel(p, text="STEAM API", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=(14, 4))

        entries = {}
        for label, key, show in [
            ("API Key", "steam_api_key", "*"),
            ("App ID", "steam_app_id", ""),
            ("Published File ID", "steam_published_file_id", ""),
        ]:
            ctk.CTkLabel(p, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(p, fg_color=COLORS.bg_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=30, show=show)
            e.insert(0, cfg.get(key, ""))
            e.pack(fill="x", padx=4, pady=(2, 7))
            entries[key] = e

        ctk.CTkLabel(p, text=f"Varsayılan şablon: {cfg.get('default_preset', self.app.template.name)}",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=(8, 2))
        ctk.CTkLabel(p, text=f"Çıktı klasörü: {self.app.output_dir}", font=make_font(TYPO.caption), text_color=COLORS.text_muted,
                     wraplength=380, justify="left").pack(anchor="w", padx=4, pady=2)

        def save():
            cfg["open_output_after_process"] = bool(open_var.get())
            cfg["auto_upload"] = bool(upload_var.get())
            cfg["steam_community_auto_submit"] = bool(community_submit_var.get())
            cfg["output_format"] = "jpg" if fmt_var.get() == "JPG" else "png"
            for key, entry in community_entries.items():
                if key == "steam_community_title_template":
                    val = entry.get()
                elif key == "steam_community_wait_after_upload_ms":
                    try: val = int(entry.get().strip())
                    except ValueError: val = 1200
                else:
                    val = entry.get().strip()
                cfg[key] = val
            for key, entry in entries.items():
                cfg[key] = entry.get().strip()
            get_config_service().save_config()
            self.app._status.ok("Ayarlar kaydedildi")

        AnimButton(p, text="Kaydet", variant="accent", height=38, text_color=COLORS.bg_0, command=save).pack(fill="x", padx=4, pady=(14, 4))

    # ════════════════════════════════════════════════════════════════════
    # Şablonlar
    # ════════════════════════════════════════════════════════════════════
    def _build_templates(self, p):
        ctk.CTkLabel(p, text="Şablonlar", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", padx=4, pady=(4, 10))

        # Yeni şablon
        new_card = ctk.CTkFrame(p, fg_color=COLORS.bg_3, corner_radius=10)
        new_card.pack(fill="x", padx=2, pady=(0, 14))
        ctk.CTkLabel(new_card, text="YENİ ŞABLON OLUŞTUR", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=12, pady=(10, 6))

        mode_var = StringVar(value="Uniform (eşit parçalar)")
        mode_map = {"Uniform (eşit parçalar)": "uniform", "Multi (farklı boyutlu parçalar)": "multi", "Single (tek parça)": "single"}
        ctk.CTkOptionMenu(new_card, values=list(mode_map), variable=mode_var,
                          fg_color=COLORS.bg_4, button_color=COLORS.accent, button_hover_color=COLORS.accent_hover,
                          dropdown_fg_color=COLORS.bg_3, dropdown_hover_color=COLORS.bg_4,
                          text_color=COLORS.text_primary, command=lambda _v: sync_mode_fields()
                          ).pack(fill="x", padx=10, pady=(0, 6))

        new_fields = {}
        row = ctk.CTkFrame(new_card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 4))
        for label, key, default in [("Parça genişliği (px)", "w", "150"), ("Parça yüksekliği (px)", "h", "1250"), ("Parça sayısı", "n", "5")]:
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True, padx=3)
            ctk.CTkLabel(col, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w")
            e = ctk.CTkEntry(col, fg_color=COLORS.bg_4, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=30)
            e.insert(0, default)
            e.pack(fill="x", pady=(2, 0))
            new_fields[key] = e

        multi_frame = ctk.CTkFrame(new_card, fg_color="transparent")
        ctk.CTkLabel(multi_frame, text="Parçalar — GENİŞLIKxYÜKSEKLİK, virgülle (ör. 506x800, 100x800)",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w")
        multi_entry = ctk.CTkEntry(multi_frame, fg_color=COLORS.bg_4, border_color=COLORS.border_default,
                                    text_color=COLORS.text_primary, height=30, placeholder_text="506x800, 100x800")
        multi_entry.pack(fill="x", pady=(2, 0))

        def sync_mode_fields():
            mode = mode_map[mode_var.get()]
            if mode == "multi":
                row.pack_forget()
                if not multi_frame.winfo_manager(): multi_frame.pack(fill="x", padx=10, pady=(0, 4), before=add_btn)
            else:
                multi_frame.pack_forget()
                if not row.winfo_manager(): row.pack(fill="x", padx=10, pady=(0, 4), before=add_btn)
                new_fields["n"].configure(state="disabled" if mode == "single" else "normal")

        def parse_multi_parts(text):
            parts = []
            for chunk in text.split(","):
                chunk = chunk.strip().lower().replace("×", "x")
                if not chunk: continue
                w_str, _, h_str = chunk.partition("x")
                parts.append({"width": int(w_str), "height": int(h_str)})
            return parts

        def create_template():
            mode = mode_map[mode_var.get()]
            try:
                if mode == "multi":
                    parts = parse_multi_parts(multi_entry.get())
                    if not parts or any(p["width"] <= 0 or p["height"] <= 0 for p in parts): raise ValueError
                    widths = "+".join(str(p["width"]) for p in parts)
                    tmpl = Template(name=f"Özel Multi ({widths})", mode="multi", parts=parts, patch=False, prefix="cus")
                else:
                    pw = int(new_fields["w"].get())
                    ph = int(new_fields["h"].get())
                    if pw <= 0 or ph <= 0: raise ValueError
                    if mode == "single":
                        tmpl = Template(name=f"Özel Tek ({pw}×{ph})", mode="single", width=pw, height=ph, patch=False, prefix="cus")
                    else:
                        cnt = int(new_fields["n"].get())
                        if cnt <= 0: raise ValueError
                        tmpl = Template(name=f"Özel ({pw}×{ph} ×{cnt})", mode="uniform", width=pw * cnt, height=ph, parts=cnt, patch=False, prefix="cus")
            except ValueError:
                self.app._status.error("Geçerli değerler gir (multi için: 506x800, 100x800 gibi)")
                return
            if any(t.name == tmpl.name for t in BUILTIN_TEMPLATES):
                self.app._status.error("Aynı isimde şablon zaten var")
                return
            BUILTIN_TEMPLATES.append(tmpl)
            self.app.template = tmpl
            save_custom_presets()
            self.app._rebuild_template_cards()
            self.app._status.set(f"Şablon eklendi: {tmpl.name}", COLORS.success, COLORS.success)
            self.open_tab("Şablonlar")

        add_btn = AnimButton(new_card, text="＋  Ekle", variant="accent", height=32, text_color=COLORS.bg_0, command=create_template)
        add_btn.pack(fill="x", padx=10, pady=(6, 10))

        # Manage existing
        ctk.CTkLabel(p, text="ŞABLONU YÖNET", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=(0, 6))

        names = [t.name for t in BUILTIN_TEMPLATES]
        selected = StringVar(value=self.app.template.name)
        menu = ctk.CTkOptionMenu(p, values=names, variable=selected,
            fg_color=COLORS.bg_3, button_color=COLORS.accent, button_hover_color=COLORS.accent_hover,
            dropdown_fg_color=COLORS.bg_3, dropdown_hover_color=COLORS.bg_4, text_color=COLORS.text_primary)
        menu.pack(fill="x", padx=4, pady=(0, 12))

        fields = {}
        for label, key in [("Ad", "name"), ("Toplam genişlik", "width"), ("Referans yükseklik", "height"), ("Parça sayısı", "parts"), ("Prefix", "prefix")]:
            ctk.CTkLabel(p, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=4)
            e = ctk.CTkEntry(p, fg_color=COLORS.bg_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=30)
            e.pack(fill="x", padx=4, pady=(2, 7))
            fields[key] = e

        patch_var = BooleanVar(value=False)
        ctk.CTkCheckBox(p, text="PNG son byte patch", variable=patch_var, font=make_font(TYPO.body_md),
                        text_color=COLORS.text_primary, fg_color=COLORS.accent, hover_color=COLORS.accent_hover,
                        checkmark_color=COLORS.bg_0).pack(anchor="w", padx=4, pady=4)

        def current_template():
            return next((t for t in BUILTIN_TEMPLATES if t.name == selected.get()), None)

        def fill(_=None):
            t = current_template()
            if not t: return
            mode = t.mode
            is_uniform = mode == "uniform"
            editable = (t.prefix not in ("work", "art", "shot") and mode in ("uniform", "single"))
            for key, entry in fields.items():
                entry.configure(state="normal"); entry.delete(0, "end")
            fields["name"].insert(0, t.name)
            fields["width"].insert(0, str(t.width))
            fields["height"].insert(0, str(t.height))
            fields["parts"].insert(0, str(t.parts) if is_uniform else "")
            fields["prefix"].insert(0, t.prefix)
            patch_var.set(t.patch)
            state = "normal" if editable else "disabled"
            for key, entry in fields.items():
                entry.configure(state="disabled" if (key == "parts" and not is_uniform) else state)

        menu.configure(command=fill)
        fill()

        def set_default():
            t = current_template()
            if not t: return
            self.app.template = t
            get_config_service().update_config(default_preset=t.name)
            self.app._sync_cards()
            self.app._status.ok("Varsayılan şablon kaydedildi")

        def save_edit():
            t = current_template()
            mode = t.mode if t else "uniform"
            if not t or t.prefix in ("work", "art", "shot"):
                self.app._status.error("Yerleşik şablonlar düzenlenemez"); return
            if mode == "multi":
                self.app._status.error("Multi şablonu düzenlemek için silip yeniden oluştur"); return
            try:
                name = fields["name"].get().strip()
                width = int(fields["width"].get())
                height = int(fields["height"].get())
                parts = int(fields["parts"].get()) if mode == "uniform" else 0
                prefix = fields["prefix"].get().strip() or "cus"
                if not name or width <= 0 or height <= 0 or (mode == "uniform" and parts <= 0): raise ValueError
            except ValueError:
                self.app._status.error("Şablon değerleri geçersiz"); return
            t.name = name; t.width = width; t.height = height; t.patch = patch_var.get(); t.prefix = prefix
            if mode == "uniform": t.parts = parts
            save_custom_presets()
            self.app.template = t
            self.app._rebuild_template_cards()
            self.app._status.ok("Şablon güncellendi")
            self.open_tab("Şablonlar")

        def delete_template():
            t = current_template()
            if not t or t.prefix in ("work", "art", "shot"):
                self.app._status.error("Yerleşik şablon silinemez"); return
            if not messagebox.askyesno("Şablonu Sil", f"{t.name} silinsin mi?"): return
            BUILTIN_TEMPLATES.remove(t)
            if self.app.template is t or self.app.template.get("name") == t.get("name"):
                self.app.template = BUILTIN_TEMPLATES[0]
            save_custom_presets()
            self.app._rebuild_template_cards()
            self.app._status.ok("Şablon silindi")
            self.open_tab("Şablonlar")

        btns = ctk.CTkFrame(p, fg_color="transparent")
        btns.pack(fill="x", padx=4, pady=(8, 4))
        AnimButton(btns, text="Varsayılan Yap", height=32, command=set_default).pack(fill="x", pady=3)
        AnimButton(btns, text="Düzenle", variant="accent", height=32, text_color=COLORS.bg_0, command=save_edit).pack(fill="x", pady=3)
        AnimButton(btns, text="Sil", nc=COLORS.bg_3, hc=COLORS.bg_4, height=32, text_color=COLORS.error, command=delete_template).pack(fill="x", pady=3)

    # ═════════════════════════════════════════════════════════════════════
    # Şablon Yönetimi (Gelişmiş)
    # ═════════════════════════════════════════════════════════════════════

    def _build_template_manager(self, p):
        """Gelişmiş Şablon Yönetimi sekmesi — Create/Read/Update/Delete + Import/Export."""
        # Embed the full TemplateManagerPage
        self._template_manager = TemplateManagerPage(p, self.app, lambda: None)
        self._template_manager.grid(row=0, column=0, sticky="nsew")
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(0, weight=1)

    # ═════════════════════════════════════════════════════════════════════
    # Geçmiş
    # ════════════════════════════════════════════════════════════════════
    def _build_history(self, p):
        ctk.CTkLabel(p, text="Upload Geçmişi", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", padx=4, pady=(4, 6))
        ctk.CTkLabel(p, text="Her manuel upload ve kuyruk projesi burada kayıtlı — 'bunu Steam'e yüklemiş miydim?' sorusunun cevabı.",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted, wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 12))

        records = load_history()
        if not records:
            ctk.CTkLabel(p, text="Henüz upload kaydı yok.", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=8)
            return

        def wipe():
            if not messagebox.askyesno("Geçmişi Temizle", f"{len(records)} kayıt silinecek. Emin misin?"): return
            clear_history()
            self.app._status.ok("Upload geçmişi temizlendi")
            self.open_tab("Geçmiş")

        AnimButton(p, text="Geçmişi Temizle", height=30, text_color=COLORS.error,
                   font=make_font(TYPO.body_md), command=wipe).pack(fill="x", padx=2, pady=(0, 10))

        state_style = {"done": ("✓ tamamlandı", COLORS.success), "failed": ("✗ başarısız", COLORS.error), "yarıda": ("⏸ yarıda kaldı", COLORS.accent_hover)}
        for rec in reversed(records):
            row = ctk.CTkFrame(p, fg_color=COLORS.bg_3, corner_radius=8)
            row.pack(fill="x", padx=2, pady=3)
            try: when = time.strftime("%d.%m.%Y %H:%M", time.localtime(float(rec.get("time", 0))))
            except: when = "?"
            source = "Kuyruk" if rec.get("source") == "kuyruk" else "Manuel"
            label = rec.get("label", "?")
            files = rec.get("files", 0)
            completed = rec.get("completed", 0)
            state_text, state_color = state_style.get(rec.get("state", ""), (rec.get("state", "?"), COLORS.text_muted))
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=10, pady=6)
            ctk.CTkLabel(left, text=f"{label}", font=make_font(TYPO.body_md, weight="bold"), text_color=COLORS.text_primary, anchor="w").pack(anchor="w")
            ctk.CTkLabel(left, text=f"{when} · {source} · {completed}/{files} parça", font=make_font(TYPO.caption), text_color=COLORS.text_muted, anchor="w").pack(anchor="w")
            ctk.CTkLabel(row, text=state_text, font=make_font(TYPO.caption, weight="bold"), text_color=state_color).pack(side="right", padx=12)

    # ════════════════════════════════════════════════════════════════════
    # Profiller
    # ════════════════════════════════════════════════════════════════════
    def _build_profiles(self, p):
        cfg = FlatConfig(get_config_service().config)
        ctk.CTkLabel(p, text="Profiller", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", padx=4, pady=(4, 6))
        ctk.CTkLabel(p, text="Şablon + Border FX + upload ayarını tek profil olarak kaydet, sonra tek tıkla uygula.",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted, wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 12))

        # Create
        new_card = ctk.CTkFrame(p, fg_color=COLORS.bg_3, corner_radius=10)
        new_card.pack(fill="x", padx=2, pady=(0, 14))
        ctk.CTkLabel(new_card, text="MEVCUT AYARLARDAN PROFİL OLUŞTUR", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=12, pady=(10, 6))
        name_entry = ctk.CTkEntry(new_card, fg_color=COLORS.bg_4, border_color=COLORS.border_default,
                                  text_color=COLORS.text_primary, height=32, placeholder_text="Profil adı (ör. Vitrin + Kırmızı Border)")
        name_entry.pack(fill="x", padx=10, pady=(0, 8))

        def create_profile():
            name = name_entry.get().strip()
            if not name: self.app._status.error("Profil adı gir"); return
            profiles = load_profiles()
            profiles[name] = {"template_name": self.app.template.name}
            for key in ("autocrop_enabled", "border_fx_enabled", "border_fx_template", "border_fx_color",
                        "border_fx_opacity", "border_fx_glow", "text_overlay_enabled", "text_overlay_text",
                        "text_overlay_color", "text_overlay_size", "text_overlay_position", "text_overlay_opacity",
                        "auto_enhance_enabled", "auto_enhance_intensity", "auto_upload", "steam_community_auto_submit"):
                profiles[name][key] = cfg.get(key)
            save_profiles(profiles)
            self.app._status.ok(f"Profil kaydedildi: {name}")
            self.open_tab("Profiller")

        AnimButton(new_card, text="＋  Profil Olarak Kaydet", variant="accent", height=32, text_color=COLORS.bg_0, command=create_profile).pack(fill="x", padx=10, pady=(0, 10))

        # List
        ctk.CTkLabel(p, text="KAYITLI PROFİLLER", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=(0, 6))
        profiles = load_profiles()
        if not profiles:
            ctk.CTkLabel(p, text="Henüz profil yok.", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=8)
            return

        def apply_profile(name, data):
            tmpl = next((t for t in BUILTIN_TEMPLATES if t.name == data.get("template_name")), None)
            if tmpl: self.app.template = tmpl; self.app._sync_cards()
            for key in ("autocrop_enabled", "border_fx_enabled", "border_fx_template", "border_fx_color",
                        "border_fx_opacity", "border_fx_glow", "text_overlay_enabled", "text_overlay_text",
                        "text_overlay_color", "text_overlay_size", "text_overlay_position", "text_overlay_opacity",
                        "auto_enhance_enabled", "auto_enhance_intensity", "auto_upload", "steam_community_auto_submit"):
                if key in data: cfg[key] = data[key]
            get_config_service().save_config()
            if self.app.current_path and os.path.isfile(self.app.current_path): self.app._load_preview(self.app.current_path)
            note = "" if tmpl else " (şablon artık yok, atlandı)"
            self.app._status.ok(f"Profil uygulandı: {name}{note}")

        def delete_profile(name):
            if not messagebox.askyesno("Profili Sil", f"'{name}' profili silinsin mi?"): return
            current = load_profiles(); current.pop(name, None); save_profiles(current)
            self.app._status.ok("Profil silindi"); self.open_tab("Profiller")

        for name, data in sorted(profiles.items()):
            row = ctk.CTkFrame(p, fg_color=COLORS.bg_3, corner_radius=8)
            row.pack(fill="x", padx=2, pady=4)
            info_bits = [data.get("template_name") or "?"]
            if data.get("border_fx_enabled"): info_bits.append("Border FX açık")
            if data.get("text_overlay_enabled"): info_bits.append("Metin açık")
            if data.get("auto_enhance_enabled"): info_bits.append("Otomatik iyileştir açık")
            if data.get("auto_upload"): info_bits.append("Auto-upload")
            ctk.CTkLabel(row, text=name, font=make_font(TYPO.body_md, weight="bold"), text_color=COLORS.text_primary, anchor="w").pack(anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(row, text="  ·  ".join(info_bits), font=make_font(TYPO.caption), text_color=COLORS.text_muted, anchor="w").pack(anchor="w", padx=12, pady=(0, 6))
            btns = ctk.CTkFrame(row, fg_color="transparent")
            btns.pack(fill="x", padx=10, pady=(0, 8))
            AnimButton(btns, text="Uygula", variant="accent", height=28, text_color=COLORS.bg_0,
                       command=lambda n=name, d=data: apply_profile(n, d)).pack(side="left", fill="x", expand=True, padx=(0, 4))
            AnimButton(btns, text="Sil", nc=COLORS.bg_4, hc=COLORS.bg_5, height=28, text_color=COLORS.error,
                       command=lambda n=name: delete_profile(n)).pack(side="left", fill="x", expand=True, padx=(4, 0))

    # ════════════════════════════════════════════════════════════════════
    # Projeler
    # ════════════════════════════════════════════════════════════════════
    def _build_projects(self, p):
        ctk.CTkLabel(p, text="Projeler", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", padx=4, pady=(4, 6))
        ctk.CTkLabel(p, text="Birden fazla Workshop öğesi üzerinde çalışıyorsan: hangi dosya(lar)/şablon/çıktı klasörüyle kaldığını kaydet, sonra tek tıkla o duruma geri dön.",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted, wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 12))

        app = self.app

        # Create
        new_card = ctk.CTkFrame(p, fg_color=COLORS.bg_3, corner_radius=10)
        new_card.pack(fill="x", padx=2, pady=(0, 14))
        ctk.CTkLabel(new_card, text="MEVCUT DURUMDAN PROJE OLUŞTUR", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=12, pady=(10, 6))

        current_desc = "Giriş seçilmedi"
        if app._batch_files: current_desc = f"{len(app._batch_files)} dosya (toplu)"
        elif app.current_path and os.path.isdir(app.current_path): current_desc = f"Klasör: {os.path.basename(app.current_path)}"
        elif app.current_path and os.path.isfile(app.current_path): current_desc = f"Dosya: {os.path.basename(app.current_path)}"
        ctk.CTkLabel(new_card, text=f"Şu an: {current_desc}  ·  {app.template.name}",
                     font=make_font(TYPO.caption), text_color=COLORS.accent, wraplength=400, justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        name_entry = ctk.CTkEntry(new_card, fg_color=COLORS.bg_4, border_color=COLORS.border_default,
                                  text_color=COLORS.text_primary, height=32, placeholder_text="Proje adı (ör. Kılıç Modu v2)")
        name_entry.pack(fill="x", padx=10, pady=(0, 6))
        note_entry = ctk.CTkEntry(new_card, fg_color=COLORS.bg_4, border_color=COLORS.border_default,
                                  text_color=COLORS.text_primary, height=32, placeholder_text="Not (opsiyonel)")
        note_entry.pack(fill="x", padx=10, pady=(0, 6))
        url_entry = ctk.CTkEntry(new_card, fg_color=COLORS.bg_4, border_color=COLORS.border_default,
                                 text_color=COLORS.text_primary, height=32, placeholder_text="Bu Workshop öğesinin upload URL'i (boşsa genel ayar kullanılır)")
        url_entry.pack(fill="x", padx=10, pady=(0, 8))

        def create_project():
            name = name_entry.get().strip()
            if not name: app._status.error("Proje adı gir"); return
            if not app._batch_files and not (app.current_path and (os.path.isfile(app.current_path) or os.path.isdir(app.current_path))):
                app._status.error("Önce bir dosya/klasör seç"); return
            entry = {"template_name": app.template.name, "output_dir": app.output_dir,
                     "note": note_entry.get().strip()}
            url = url_entry.get().strip()
            if url: entry["steam_community_upload_url"] = url
            if app._batch_files: entry["input_paths"] = list(app._batch_files)
            elif os.path.isdir(app.current_path): entry["input_dir"] = app.current_path
            else: entry["input_paths"] = [app.current_path]
            pfid = app._cfg.get("steam_published_file_id", "").strip()
            if pfid: entry["steam_published_file_id"] = pfid
            entry["effects"] = {k: app._cfg.get(k) for k in ("autocrop_enabled", "border_fx_enabled", "border_fx_template", "border_fx_color",
                                                             "border_fx_opacity", "border_fx_glow", "text_overlay_enabled", "text_overlay_text",
                                                             "text_overlay_color", "text_overlay_size", "text_overlay_position", "text_overlay_opacity",
                                                             "auto_enhance_enabled", "auto_enhance_intensity", "auto_upload", "steam_community_auto_submit")}
            projects = load_projects()
            projects[name] = entry
            save_projects(projects)
            app._status.ok(f"Proje kaydedildi: {name}")
            self.open_tab("Projeler")

        AnimButton(new_card, text="＋  Proje Olarak Kaydet", variant="accent", height=32, text_color=COLORS.bg_0, command=create_project).pack(fill="x", padx=10, pady=(0, 10))

        # List
        ctk.CTkLabel(p, text="KAYITLI PROJELER", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=(0, 6))

        # Cloud Sync — Export/Import row
        sync_row = ctk.CTkFrame(p, fg_color="transparent")
        sync_row.pack(fill="x", padx=2, pady=(0, 8))
        sync_row.grid_columnconfigure((0, 1), weight=1)

        def export_projects():
            try:
                import json as _json
                from tkinter import filedialog as _fd
                data = {
                    "version": "2.1.0",
                    "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "projects": load_projects(),
                    "profiles": load_profiles(),
                }
                # Also include custom presets (non-builtin)
                try:
                    from steameditor.core.models import BUILTIN_TEMPLATES
                    builtin_names = {t.name for t in BUILTIN_TEMPLATES}
                    customs = [t for t in BUILTIN_TEMPLATES if t.name not in builtin_names]
                    # Fallback: legacy TEMPLATES
                    if not customs:
                        from steameditor.config import TEMPLATES as _T
                        customs = [t for t in _T if t.get("prefix") not in ("work", "art", "shot")]
                    data["presets"] = customs
                except Exception:
                    pass
                path = _fd.asksaveasfilename(
                    title="Projeleri Dışa Aktar",
                    defaultextension=".json",
                    filetypes=[("JSON", "*.json"), ("Tüm Dosyalar", "*.*")],
                    initialfile=f"splitforge_export_{time.strftime('%Y%m%d_%H%M')}.json",
                )
                if not path:
                    return
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(data, f, ensure_ascii=False, indent=2)
                self.app._status.ok(f"Dışa aktarıldı: {os.path.basename(path)} ({len(data['projects'])} proje)")
            except Exception as e:
                self.app._status.error(f"Dışa aktarma hatası: {e}")

        def import_projects():
            try:
                import json as _json
                from tkinter import filedialog as _fd
                path = _fd.askopenfilename(
                    title="Projeleri İçe Aktar",
                    filetypes=[("JSON", "*.json"), ("Tüm Dosyalar", "*.*")],
                )
                if not path or not os.path.isfile(path):
                    return
                with open(path, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                incoming_projects = data.get("projects") if isinstance(data, dict) and "projects" in data else (data if isinstance(data, dict) else {})
                if not isinstance(incoming_projects, dict):
                    self.app._status.error("Dosya formatı geçersiz (projects dict bekleniyor)")
                    return
                # Merge: existing + incoming (incoming overwrites same name)
                current = load_projects()
                merged_count = 0
                for k, v in incoming_projects.items():
                    if isinstance(v, dict):
                        current[k] = v
                        merged_count += 1
                save_projects(current)
                # Profiles if present
                if isinstance(data, dict) and "profiles" in data and isinstance(data["profiles"], dict):
                    cur_prof = load_profiles()
                    for k, v in data["profiles"].items():
                        if isinstance(v, dict):
                            cur_prof[k] = v
                    save_profiles(cur_prof)
                self.app._status.ok(f"İçe aktarıldı: {merged_count} proje (toplam {len(current)})")
                self.open_tab("Projeler")
            except Exception as e:
                self.app._status.error(f"İçe aktarma hatası: {e}")

        AnimButton(sync_row, text="📤  Dışa Aktar", nc=COLORS.bg_3, hc=COLORS.bg_4, height=30, corner_radius=8,
                   font=make_font(TYPO.body_sm, weight="bold"), text_color=COLORS.text_primary,
                   command=export_projects).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        AnimButton(sync_row, text="📥  İçe Aktar", nc=COLORS.bg_3, hc=COLORS.bg_4, height=30, corner_radius=8,
                   font=make_font(TYPO.body_sm, weight="bold"), text_color=COLORS.accent,
                   command=import_projects).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ctk.CTkLabel(p, text="Cloud Sync: Dosyayı Drive/Discord ile paylaş, diğer cihazda İçe Aktar ile yükle.",
                     font=make_font(TYPO.caption), text_color=COLORS.text_muted, wraplength=420, justify="left").pack(anchor="w", padx=4, pady=(0, 8))

        projects = load_projects()
        if not projects:
            ctk.CTkLabel(p, text="Henüz proje yok.", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=4, pady=8)
            return

        def open_project(name, data):
            if "input_dir" in data and os.path.isdir(data["input_dir"]):
                app._batch_files = None; app.current_path = data["input_dir"]; app._drop.reset()
            elif "input_paths" in data:
                valid = [pp for pp in data["input_paths"] if os.path.isfile(pp)]
                if len(valid) == 1: app._on_file_drop(valid[0])
                elif len(valid) > 1: app._on_batch_drop(valid)
                else: app._status.error("Proje dosyaları artık bulunamıyor"); return
            tmpl = next((t for t in BUILTIN_TEMPLATES if t.name == data.get("template_name")), None)
            if tmpl: app.template = tmpl; app._sync_cards()
            if data.get("output_dir") and os.path.isdir(data["output_dir"]):
                app.output_dir = data["output_dir"]; app._out_lbl.configure(text=app._short_path(app.output_dir))
            cfg_changed = False
            if data.get("steam_published_file_id"): app._cfg["steam_published_file_id"] = data["steam_published_file_id"]; cfg_changed = True
            if data.get("steam_community_upload_url"): app._cfg["steam_community_upload_url"] = data["steam_community_upload_url"]; cfg_changed = True
            effects = data.get("effects")
            if isinstance(effects, dict):
                for k in ("autocrop_enabled", "border_fx_enabled", "border_fx_template", "border_fx_color",
                          "border_fx_opacity", "border_fx_glow", "text_overlay_enabled", "text_overlay_text",
                          "text_overlay_color", "text_overlay_size", "text_overlay_position", "text_overlay_opacity",
                          "auto_enhance_enabled", "auto_enhance_intensity", "auto_upload", "steam_community_auto_submit"):
                    if k in effects and effects[k] is not None: app._cfg[k] = effects[k]
                cfg_changed = True
            if cfg_changed: get_config_service().save_config()
            note = f" — {data['note']}" if data.get("note") else ""
            app._status.ok(f"Proje açıldı: {name}{note}")

        def delete_project(name):
            if not messagebox.askyesno("Projeyi Sil", f"'{name}' projesi silinsin mi?"): return
            current = load_projects(); current.pop(name, None); save_projects(current)
            app._status.ok("Proje silindi"); self.open_tab("Projeler")

        # Queue button
        queue_vars = {}
        def start_queue():
            selected = [n for n, v in queue_vars.items() if v.get()]
            if not selected: app._status.error("Kuyruğa en az bir proje seç"); return
            app._start_project_queue(selected)
        if len(projects) > 1:
            AnimButton(p, text="🚀  Seçili Projeleri Kuyruğa Al ve Başlat", variant="accent", height=34, text_color=COLORS.bg_0,
                       command=start_queue).pack(fill="x", padx=2, pady=(0, 8))

        for name, data in sorted(projects.items()):
            row = ctk.CTkFrame(p, fg_color=COLORS.bg_3, corner_radius=8)
            row.pack(fill="x", padx=2, pady=4)
            if "input_dir" in data: src_desc = f"Klasör: {os.path.basename(data['input_dir'])}"
            else:
                n = len(data.get("input_paths", []))
                src_desc = f"{n} dosya" if n != 1 else os.path.basename(data.get("input_paths", ["?"])[0])
            info_bits = [src_desc, data.get("template_name") or "?"]
            if data.get("steam_community_upload_url"): info_bits.append("özel upload URL")
            if data.get("note"): info_bits.append(data["note"])
            header_row = ctk.CTkFrame(row, fg_color="transparent")
            header_row.pack(fill="x", padx=12, pady=(8, 0))
            qvar = BooleanVar(value=False)
            queue_vars[name] = qvar
            if len(projects) > 1:
                ctk.CTkCheckBox(header_row, text="", variable=qvar, width=20, fg_color=COLORS.accent,
                                hover_color=COLORS.accent_hover, checkmark_color=COLORS.bg_0).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(header_row, text=name, font=make_font(TYPO.body_md, weight="bold"), text_color=COLORS.text_primary, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text="  ·  ".join(info_bits), font=make_font(TYPO.caption), text_color=COLORS.text_muted, anchor="w", wraplength=380, justify="left").pack(anchor="w", padx=12, pady=(0, 6))
            btns = ctk.CTkFrame(row, fg_color="transparent")
            btns.pack(fill="x", padx=10, pady=(0, 8))
            AnimButton(btns, text="Aç", variant="accent", height=28, text_color=COLORS.bg_0,
                       command=lambda n=name, d=data: open_project(n, d)).pack(side="left", fill="x", expand=True, padx=(0, 4))
            AnimButton(btns, text="Sil", nc=COLORS.bg_4, hc=COLORS.bg_5, height=28, text_color=COLORS.error,
                       command=lambda n=name: delete_project(n)).pack(side="left", fill="x", expand=True, padx=(4, 0))

    # ════════════════════════════════════════════════════════════════════
    # Notlar
    # ════════════════════════════════════════════════════════════════════
    def _autosave_notes(self):
        if self._notes_txt is None: return
        try:
            with open(self._notes_path, "w", encoding="utf-8") as f:
                f.write(self._notes_txt.get("1.0", "end-1c"))
        except Exception: pass
        self._notes_txt = None

    def _build_notes(self, p):
        ctk.CTkLabel(p, text="📋  Steam Yardımcı Paneli", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", padx=4, pady=(4, 10))

        tabs = ctk.CTkTabview(p, fg_color=COLORS.bg_1, height=560,
            segmented_button_selected_color=COLORS.accent, segmented_button_selected_hover_color=COLORS.accent_hover,
            segmented_button_unselected_color=COLORS.bg_3, segmented_button_unselected_hover_color=COLORS.bg_4,
            text_color=COLORS.text_primary)
        tabs.pack(fill="both", expand=True, padx=0, pady=(0, 8))
        helper_tab = tabs.add("Yardımcı")
        notes_tab = tabs.add("Notlar")

        helper = ctk.CTkScrollableFrame(helper_tab, fg_color=COLORS.bg_2, corner_radius=10,
            scrollbar_button_color=COLORS.bg_4, scrollbar_button_hover_color=COLORS.accent)
        helper.pack(fill="both", expand=True, padx=4, pady=4)

        ctk.CTkLabel(helper, text="CONSOLE KODLARI", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=14, pady=(14, 6))
        preferred = TEMPLATE_SNIPPET_HINTS.get(self.app.template.mode)
        for title, snippet in STEAM_CONSOLE_SNIPPETS:
            is_preferred = title == preferred
            row = ctk.CTkFrame(helper, fg_color=COLORS.bg_4 if is_preferred else COLORS.bg_3,
                               border_width=2 if is_preferred else 0, border_color=COLORS.accent, corner_radius=8)
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=title, font=make_font(TYPO.body_md, weight="bold"), text_color=COLORS.text_primary, anchor="w").pack(side="left", fill="x", expand=True, padx=10, pady=8)
            AnimButton(row, text="Kopyala", nc=COLORS.accent, hc=COLORS.accent_hover, variant="accent",
                       height=28, corner_radius=6, font=make_font(TYPO.caption), text_color=COLORS.bg_0,
                       command=lambda s=snippet, t=title: self.app._copy_clipboard(s, t)).pack(side="right", padx=8, pady=6)

        ctk.CTkLabel(helper, text="HIZLI LİNKLER", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=14, pady=(14, 6))
        links_grid = ctk.CTkFrame(helper, fg_color="transparent")
        links_grid.pack(fill="x", padx=10, pady=(0, 8))
        links_grid.grid_columnconfigure((0, 1), weight=1)
        for i, (title, url) in enumerate(STEAM_HELPER_LINKS):
            AnimButton(links_grid, text=title, nc=COLORS.bg_3, hc=COLORS.bg_4, height=32, corner_radius=8,
                       font=make_font(TYPO.caption), text_color=COLORS.text_primary,
                       command=lambda u=url: webbrowser.open(u)).grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)

        ctk.CTkLabel(helper, text="UPLOAD CHECKLIST", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=14, pady=(14, 6))
        for step in STEAM_UPLOAD_STEPS:
            ctk.CTkCheckBox(helper, text=step, font=make_font(TYPO.body_md),
                            text_color=COLORS.text_primary, fg_color=COLORS.accent, hover_color=COLORS.accent_hover,
                            checkmark_color=COLORS.bg_0).pack(anchor="w", padx=16, pady=4)

        txt = Text(notes_tab, bg=COLORS.bg_2, fg=COLORS.text_primary, insertbackground=COLORS.accent,
                   font=("Consolas", 10), wrap="word", undo=True, relief="flat", padx=12, pady=12,
                   selectbackground=COLORS.accent, selectforeground=COLORS.bg_0)
        txt.pack(fill="both", expand=True, padx=4, pady=4)
        if os.path.exists(self._notes_path):
            try:
                with open(self._notes_path, "r", encoding="utf-8") as f:
                    txt.insert("1.0", f.read())
            except: pass
        self._notes_txt = txt

        def save_now():
            self._autosave_notes()
            self._notes_txt = txt
            self.app._status.ok("Notlar kaydedildi")
        AnimButton(notes_tab, text="Kaydet", nc=COLORS.accent, hc=COLORS.accent_hover, variant="accent",
                   height=32, text_color=COLORS.bg_0, command=save_now).pack(fill="x", pady=(6, 0))

    # ════════════════════════════════════════════════════════════════════
    # Helper
    # ════════════════════════════════════════════════════════════════════
    def _short_path(self, p):
        parts = str(p).replace("\\", "/").split("/")
        if len(parts) > 3: return "…/" + "/".join(parts[-2:])
        return str(p)