"""steameditor.ui.pages.template_manager — Comprehensive Template Management UI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageDraw

from steameditor.core.models import Template, MultiPart, BUILTIN_TEMPLATES, DEFAULT_TEMPLATE, uniform_slice_bounds
from steameditor.config import save_custom_presets, load_custom_presets
from steameditor.core.processor import render_template_preview
from steameditor.ui.design_system import (
    COLORS, SPACING, TYPO, RADIUS, make_font, make_ctk_image, apply_glass,
)
from steameditor.ui.components import AnimButton

from tkinter import BooleanVar


class TemplateManagerPage(ctk.CTkFrame):
    """Comprehensive Template Management UI."""

    def __init__(self, master, app, on_back, **kw):
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 2)
        super().__init__(master, fg_color=COLORS.bg_2, border_color=COLORS.border_default, **kw)
        self.app = app
        self._on_back = on_back
        self._selected_template: Optional[Template] = None
        self._preview_image = None
        self._preview_tk = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS.bg_3, corner_radius=0, height=44)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="🧩  Şablon Yönetimi", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(side="left", padx=14)
        AnimButton(hdr, text="← Geri", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28, corner_radius=6,
                   font=make_font(TYPO.body_md), text_color=COLORS.text_muted, command=self._back).pack(side="right", padx=10, pady=8)

        # Nav
        nav = ctk.CTkFrame(self, fg_color=COLORS.bg_1, width=180, corner_radius=0)
        nav.grid(row=1, column=0, sticky="nsw")
        nav.grid_propagate(False)

        ctk.CTkLabel(nav, text="ŞABLONLAR", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=16, pady=(16, 8))

        self._template_list = ctk.CTkScrollableFrame(nav, fg_color="transparent",
            scrollbar_button_color=COLORS.bg_4, scrollbar_button_hover_color=COLORS.accent)
        self._template_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._template_list.grid_columnconfigure(0, weight=1)

        # Buttons
        btn_frame = ctk.CTkFrame(nav, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=8)
        AnimButton(btn_frame, text="+ Yeni Şablon", variant="accent", height=36, text_color=COLORS.bg_0,
                   command=self._new_template).pack(fill="x", pady=2)
        AnimButton(btn_frame, text="📥 İçe Aktar", nc=COLORS.bg_3, hc=COLORS.bg_4, height=32,
                   command=self._import_templates).pack(fill="x", pady=2)
        AnimButton(btn_frame, text="📤 Dışa Aktar", nc=COLORS.bg_3, hc=COLORS.bg_4, height=32,
                   command=self._export_templates).pack(fill="x", pady=2)

        # Content area
        self._content = ctk.CTkScrollableFrame(self, fg_color="transparent",
            scrollbar_button_color=COLORS.bg_4, scrollbar_button_hover_color=COLORS.accent)
        self._content.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))

        self._build_welcome()

    def _back(self):
        self._on_back()

    # ══════════════════════════════════════════════════════════════════════
    # List View
    # ══════════════════════════════════════════════════════════════════════



    def _get_template_by_name(self, name: str):
        for t in BUILTIN_TEMPLATES:
            if t.name == name:
                return t
        return None

    def _get_template_object_from_name(self, name):
        return self._get_template_by_name(name)

    def _get_template_name_from_object(self, obj):
        return obj.name if hasattr(obj, 'name') else str(obj)


    def _format_dimensions(self, tmpl: Template) -> str:
        if tmpl.mode == "uniform":
            bounds = uniform_slice_bounds(tmpl.width, tmpl.parts if isinstance(tmpl.parts, int) else 5)
            pw = bounds[0][1] - bounds[0][0]
            return f"📐 {tmpl.width}×{tmpl.height}px  ·  {tmpl.parts if isinstance(tmpl.parts, int) else len(tmpl.parts)} parça  ·  ~{bounds[0][1]-bounds[0][0]}px/parça"
        elif tmpl.mode == "multi":
            parts = tmpl.parts if isinstance(tmpl.parts, list) else []
            dims = " + ".join(f"{p.width}×{p.height}" for p in parts)
            total_w = sum(p.width for p in parts)
            max_h = max(p.height for p in parts) if parts else 0
            return f"📐 Toplam {total_w}×{max_h}px  ·  Parçalar: {dims}"
        else:
            return f"📐 {tmpl.width}×{tmpl.height}px"

    def _refresh_template_list(self):
        for w in self._template_list.winfo_children():
            w.destroy()

        for tmpl in BUILTIN_TEMPLATES:
            self._create_template_list_item(tmpl)

    def _create_template_list_item(self, tmpl: Template):
        is_builtin = tmpl.prefix in ("work", "art", "shot")
        is_selected = self._selected_template is tmpl

        # Main card
        tmpl_frame = ctk.CTkFrame(self._template_list, fg_color=COLORS.bg_3, corner_radius=8, border_width=2,
                            border_color=COLORS.accent_500 if self._selected_template is not None and self._selected_template is tmpl else COLORS.border_default)
        tmpl_frame.pack(fill="x", padx=8, pady=3)

        # Make entire card clickable
        for w in (tmpl_frame,):
            try:
                tmpl_frame.bind("<Button-1>", lambda e, t=tmpl: self._select_template(tmpl))
            except:
                pass

        # Header with icon and name
        header = ctk.CTkFrame(tmpl_frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))

        icons = {"uniform": "⚡", "multi": "✏️", "single": "🖼"}
        icon = icons.get(tmpl.mode, "◆")

        ctk.CTkLabel(header, text=icons.get(tmpl.mode, "◆"), font=ctk.CTkFont("Segoe UI Emoji", 20), text_color=COLORS.accent_500).pack(side="left")
        ctk.CTkLabel(header, text=tmpl.name, font=make_font(TYPO.heading_sm), text_color=COLORS.text_primary, wraplength=200).pack(side="left", padx=(8, 0), anchor="n")

        # Preview frame
        preview_frame = ctk.CTkFrame(tmpl_frame, fg_color="transparent")
        preview_frame.pack(fill="x", padx=12, pady=(0, 4))

        # Badges
        badges = []
        if tmpl.patch:
            badges.append("🔧 Patch")
        if tmpl.mode == "uniform":
            badges.append(f"⚡ {tmpl.parts if isinstance(tmpl.parts, int) else len(tmpl.parts)} parçalı")
        elif tmpl.mode == "multi":
            badges.append(f"✏️ {len(tmpl.parts)} parça")
        else:
            badges.append("🖼 Tek parça")
        if tmpl.prefix:
            badges.append(f"🏷 {tmpl.prefix}")

        badge_frame = ctk.CTkFrame(tmpl_frame, fg_color="transparent")
        badge_frame.pack(fill="x", padx=12, pady=(0, 4))
        for badge in badges:
            ctk.CTkLabel(badge_frame, text=badge, font=make_font(TYPO.caption), text_color=COLORS.accent_400,
                         fg_color=COLORS.accent_subtle, corner_radius=4, padx=6, pady=1).pack(side="left", padx=2)

        # Dimensions
        dim_text = self._format_dimensions(tmpl)
        ctk.CTkLabel(tmpl_frame, text=dim_text, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=12, pady=(0, 8))

        # Actions
        actions = ctk.CTkFrame(tmpl_frame, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(4, 10))

        def make_select(t=tmpl):
            return lambda: self._select_template(t)

        AnimButton(actions, text="Seç", variant="accent", height=28, text_color=COLORS.bg_0,
                   command=make_select).pack(side="left", fill="x", expand=True, padx=(0, 4))

        if tmpl.prefix not in ("work", "art", "shot"):
            AnimButton(actions, text="Düzenle", nc=COLORS.bg_3, hc=COLORS.bg_4, height=28,
                       command=lambda: self._edit_template(tmpl)).pack(side="left", fill="x", expand=True, padx=4)
            AnimButton(actions, text="Sil", nc=COLORS.bg_4, hc=COLORS.bg_5, height=28, text_color=COLORS.error,
                       command=lambda t=tmpl: self._delete_template(t)).pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            ctk.CTkLabel(actions, text="Yerleşik — düzenlenemez/silinemez", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(fill="x", padx=4)

    def _format_dimensions(self, tmpl: Template) -> str:
        if tmpl.mode == "uniform":
            bounds = uniform_slice_bounds(tmpl.width, tmpl.parts if isinstance(tmpl.parts, int) else 5)
            pw = bounds[0][1] - bounds[0][0]
            return f"📐 {tmpl.width}×{tmpl.height}px  ·  {tmpl.parts if isinstance(tmpl.parts, int) else len(tmpl.parts)} parça  ·  ~{bounds[0][1]-bounds[0][0]}px/parça"
        elif tmpl.mode == "multi":
            parts = tmpl.parts if isinstance(tmpl.parts, list) else []
            total_w = sum(p.width for p in parts)
            max_h = max(p.height for p in parts) if parts else 0
            dims = " + ".join(f"{p.width}×{p.height}" for p in parts)
            return f"📐 Toplam {total_w}×{max_h}px  ·  Parçalar: {dims}"
        else:
            return f"📐 {tmpl.width}×{tmpl.height}px"

    def _select_template(self, tmpl: Template):
        self._selected_template = tmpl
        self._refresh_template_list()
        self._show_template_details(tmpl)

    def _show_template_details(self, tmpl: Template):
        # Clear content
        for w in self._content.winfo_children():
            w.destroy()

        # Main detail view
        ctk.CTkLabel(self._content, text=tmpl.name, font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", padx=4, pady=(4, 12))

        # Preview
        preview = self._generate_template_preview(tmpl)
        preview_lbl = ctk.CTkLabel(self._content, text="", image=make_ctk_image(preview.resize((600, 300), Image.LANCZOS)))
        preview_lbl.pack(pady=(0, 16))
        self._preview_tk = make_ctk_image(preview.resize((600, 300), Image.LANCZOS))
        preview_lbl.configure(image=self._preview_tk)

        # Details grid
        details = ctk.CTkFrame(self._content, fg_color=COLORS.bg_2, corner_radius=RADIUS.lg)
        details.pack(fill="x", padx=4, pady=(16, 8))
        details.grid_columnconfigure((0, 1, 2, 3), weight=1)

        fields = [
            ("Mod", tmpl.mode.capitalize()),
            ("Genişlik", f"{tmpl.width} px"),
            ("Yükseklik", f"{tmpl.height} px"),
            ("Parça Sayısı", str(tmpl.parts) if isinstance(tmpl.parts, int) else str(len(tmpl.parts))),
            ("Prefix", tmpl.prefix),
            ("Patch", "Açık" if tmpl.patch else "Kapalı"),
        ]

        for i, (label, value) in enumerate(fields):
            row = i // 3
            col = i % 3
            cell = ctk.CTkFrame(details, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="ew", padx=12, pady=8)
            ctk.CTkLabel(cell, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w")
            ctk.CTkLabel(cell, text=value, font=make_font(TYPO.body_md, weight="bold"), text_color=COLORS.text_primary).pack(anchor="w")

        # Actions
        actions = ctk.CTkFrame(self._content, fg_color="transparent")
        actions.pack(fill="x", padx=4, pady=(16, 8))

        AnimButton(actions, text="✏️ Düzenle", variant="accent", height=36, text_color=COLORS.bg_0,
                   command=lambda: self._edit_template(self._get_template_object())).pack(side="left", fill="x", expand=True, padx=(0, 4))

        if tmpl.prefix not in ("work", "art", "shot"):
            AnimButton(actions, text="🗑 Sil", nc=COLORS.bg_4, hc=COLORS.bg_5, height=36, text_color=COLORS.error,
                       command=lambda: self._delete_template(tmpl)).pack(side="left", fill="x", expand=True, padx=(4, 0))

        AnimButton(actions, text="📋 Kopyala", nc=COLORS.bg_3, hc=COLORS.bg_4, height=36,
                   command=lambda: self._duplicate_template(tmpl)).pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _build_welcome(self):
        for w in self._content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._content, text="🧩  Şablon Yönetimi", font=make_font(TYPO.display_md), text_color=COLORS.text_primary).pack(pady=(40, 8))
        ctk.CTkLabel(self._content, text="Şablonlarınızı oluşturun, düzenleyin ve yönetin.\nSoldaki listeden bir şablon seçin veya yeni bir tane oluşturun.",
                     font=make_font(TYPO.body_md), text_color=COLORS.text_muted, justify="center").pack(pady=(0, 24))

        AnimButton(self._content, text="+  Yeni Şablon Oluştur", variant="accent", height=44, text_color=COLORS.bg_0,
                   command=self._new_template).pack(pady=12)

        AnimButton(self._content, text="📥 Şablon İçe Aktar (JSON)", nc=COLORS.bg_3, hc=COLORS.bg_4, height=36,
                   command=self._import_templates).pack(pady=8)

        # Quick stats
        stats = ctk.CTkFrame(self._content, fg_color=COLORS.bg_2, corner_radius=RADIUS.lg)
        stats.pack(fill="x", padx=40, pady=(24, 0))

        ctk.CTkLabel(stats, text="📊  İstatistikler", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=16, pady=(16, 8))

        stats_grid = ctk.CTkFrame(stats, fg_color="transparent")
        stats_grid.pack(fill="x", padx=16, pady=(0, 16))
        stats_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        total = len(BUILTIN_TEMPLATES)
        builtin = sum(1 for t in BUILTIN_TEMPLATES if t.prefix in ("work", "art", "shot"))
        custom = total - builtin
        modes = set(t.mode for t in BUILTIN_TEMPLATES)

        for i, (label, value) in enumerate([
            ("Toplam", str(total)),
            ("Yerleşik", str(builtin)),
            ("Özel", str(custom)),
            ("Mod Sayısı", str(len(modes))),
        ]):
            card = ctk.CTkFrame(stats_grid, fg_color=COLORS.bg_1, corner_radius=RADIUS.md)
            card.grid(row=0, column=i, sticky="ew", padx=8, pady=12)
            ctk.CTkLabel(card, text=value, font=make_font(TYPO.display_md, weight="bold"), text_color=COLORS.accent_500).pack(pady=(12, 2))
            ctk.CTkLabel(card, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(pady=(0, 12))

    # ══════════════════════════════════════════════════════════════════════
    # Template Operations
    # ══════════════════════════════════════════════════════════════════════

    def _new_template(self):
        self._open_template_editor()

    def _edit_template(self, tmpl: Template):
        self._open_template_editor(tmpl)

    def _delete_template(self, tmpl: Template):
        if tmpl.prefix in ("work", "art", "shot"):
            self.app._status.error("Yerleşik şablon silinemez")
            return
        if not messagebox.askyesno("Şablonu Sil", f"'{tmpl.name}' silinsin mi?\nBu işlem geri alınamaz."):
            return
        BUILTIN_TEMPLATES.remove(tmpl)
        if self.app.template is tmpl or self.app.template.get("name") == tmpl.name:
            self.app.template = BUILTIN_TEMPLATES[0]
        save_custom_presets()
        self.app._rebuild_template_cards()
        self._refresh_template_list()
        self._build_welcome()
        self.app._status.ok(f"Şablon silindi: {tmpl.name}")

    def _duplicate_template(self, tmpl: Template):
        new_tmpl = Template(
            name=f"{tmpl.name} (Kopya)",
            mode=tmpl.mode,
            width=tmpl.width,
            height=tmpl.height,
            parts=tmpl.parts if isinstance(tmpl.parts, list) else tmpl.parts,
            patch=tmpl.patch,
            prefix=f"{tmpl.prefix}_copy" if tmpl.prefix else "copy",
        )
        BUILTIN_TEMPLATES.append(new_tmpl)
        save_custom_presets()
        self.app._rebuild_template_cards()
        self._refresh_template_list()
        self.app._status.ok(f"Şablon kopyalandı: {new_tmpl.name}")

    def _new_template(self):
        self._open_template_editor()

    def _edit_template(self, tmpl: Template):
        self._open_template_editor(tmpl)

    def _delete_template(self, tmpl: Template):
        if tmpl.prefix in ("work", "art", "shot"):
            self.app._status.error("Yerleşik şablon silinemez")
            return
        if not messagebox.askyesno("Şablonu Sil", f"'{tmpl.name}' silinsin mi?\nBu işlem geri alınamaz."):
            return
        BUILTIN_TEMPLATES.remove(tmpl)
        if self.app.template is tmpl or self.app.template.get("name") == tmpl.name:
            self.app.template = BUILTIN_TEMPLATES[0]
        save_custom_presets()
        self.app._rebuild_template_cards()
        self._refresh_template_list()
        self._build_welcome()
        self.app._status.ok(f"Şablon silindi: {tmpl.name}")

    def _duplicate_template(self, tmpl: Template):
        new_tmpl = Template(
            name=f"{tmpl.name} (Kopya)",
            mode=tmpl.mode,
            width=tmpl.width,
            height=tmpl.height,
            parts=tmpl.parts if isinstance(tmpl.parts, list) else tmpl.parts,
            patch=tmpl.patch,
            prefix=f"{tmpl.prefix}_copy" if tmpl.prefix else "copy",
        )
        BUILTIN_TEMPLATES.append(new_tmpl)
        save_custom_presets()
        self.app._rebuild_template_cards()
        self._refresh_template_list()
        self.app._status.ok(f"Şablon kopyalandı: {new_tmpl.name}")

    # ══════════════════════════════════════════════════════════════════════
    # Template Editor Dialog
    # ══════════════════════════════════════════════════════════════════════

    def _open_template_editor(self, tmpl: Optional[Template] = None):
        is_edit = tmpl is not None
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"{'Düzenle' if tmpl else 'Yeni'} Şablon")
        dialog.geometry("600x700")
        dialog.configure(fg_color=COLORS.bg_1)
        dialog.transient(self)
        dialog.grab_set()

        # Form
        form = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(form, text="Şablon Bilgileri", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(anchor="w", pady=(0, 16))

        # Name
        ctk.CTkLabel(form, text="Ad", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", pady=(0, 4))
        name_entry = ctk.CTkEntry(form, fg_color=COLORS.bg_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=36, placeholder_text="Örn: Özel Vitrin 5-Parça")
        name_entry.pack(fill="x", pady=(0, 12))
        if tmpl: name_entry.insert(0, tmpl.name)

        # Mode
        ctk.CTkLabel(form, text="Mod", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", pady=(12, 4))
        mode_var = ctk.StringVar(value=tmpl.mode if tmpl else "uniform")
        mode_menu = ctk.CTkOptionMenu(form, values=["Uniform (eşit parçalar)", "Multi (farklı boyutlu parçalar)", "Single (tek parça)"],
            variable=ctk.StringVar(value="Uniform (eşit parçalar)" if tmpl is None or tmpl.mode == "uniform" else
                                       ("Multi (farklı boyutlu parçalar)" if tmpl.mode == "multi" else "Single (tek parça)")),
            fg_color=COLORS.surface_3, button_color=COLORS.accent, button_hover_color=COLORS.accent_hover,
            dropdown_fg_color=COLORS.surface_3, dropdown_hover_color=COLORS.surface_4,
            text_color=COLORS.text_primary)
        mode_menu.pack(fill="x", pady=(0, 12))

        # Dimensions frame
        dim_frame = ctk.CTkFrame(form, fg_color="transparent")
        dim_frame.pack(fill="x", pady=(0, 12))
        dim_frame.grid_columnconfigure((0, 1, 2), weight=1)

        def on_mode_change(choice):
            # Update UI based on mode
            pass

        # Width
        w_frame = ctk.CTkFrame(dim_frame, fg_color="transparent")
        w_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(w_frame, text="Genişlik (px)", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w")
        w_entry = ctk.CTkEntry(w_frame, fg_color=COLORS.surface_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=36)
        w_entry.pack(fill="x", pady=(4, 0))
        if tmpl: w_entry.insert(0, str(tmpl.width))

        # Height
        h_frame = ctk.CTkFrame(dim_frame, fg_color="transparent")
        h_frame.grid(row=0, column=1, sticky="ew", padx=8)
        ctk.CTkLabel(h_frame, text="Yükseklik (px)", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w")
        h_entry = ctk.CTkEntry(h_frame, fg_color=COLORS.bg_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=36)
        h_entry.pack(fill="x", pady=(4, 0))
        if tmpl: h_entry.insert(0, str(tmpl.height))

        # Parts
        p_frame = ctk.CTkFrame(dim_frame, fg_color="transparent")
        p_frame.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        ctk.CTkLabel(p_frame, text="Parça Sayısı", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w")
        parts_entry = ctk.CTkEntry(p_frame, fg_color=COLORS.surface_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=36)
        parts_entry.pack(fill="x", pady=(4, 0))
        if tmpl and isinstance(tmpl.parts, int):
            parts_entry.insert(0, str(tmpl.parts))
        else:
            parts_entry.insert(0, "5")

        # Mode selector
        mode_frame = ctk.CTkFrame(form, fg_color=COLORS.surface_2, corner_radius=RADIUS.lg)
        mode_frame.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(mode_frame, text="Mod", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=16, pady=(12, 4))
        mode_var = ctk.StringVar(value="Uniform (eşit parçalar)")
        mode_map = {"Uniform (eşit parçalar)": "uniform", "Multi (farklı boyutlu parçalar)": "multi", "Single (tek parça)": "single"}
        mode_map_rev = {v: k for k, v in mode_map.items()}
        if tmpl: mode_var.set(mode_map_rev.get(tmpl.mode, "Uniform (eşit parçalar)"))
        mode_menu = ctk.CTkOptionMenu(mode_frame, values=list(mode_map), variable=mode_var,
            fg_color=COLORS.surface_3, button_color=COLORS.accent, button_hover_color=COLORS.accent_hover,
            dropdown_fg_color=COLORS.surface_3, dropdown_hover_color=COLORS.surface_4,
            text_color=COLORS.text_primary, width=300)
        mode_menu.pack(fill="x", padx=16, pady=(0, 16))

        # Patch
        patch_var = BooleanVar(value=tmpl.patch if tmpl else False)
        ctk.CTkCheckBox(form, text="PNG son-byte patch (0x21)", variable=patch_var,
                        font=make_font(TYPO.body_md), text_color=COLORS.text_primary,
                        fg_color=COLORS.accent, hover_color=COLORS.accent_hover, checkmark_color=COLORS.bg_0).pack(anchor="w", padx=4, pady=(0, 12))

        # Prefix
        ctk.CTkLabel(form, text="Prefix (çıktı dosya adı öneki)", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", pady=(12, 4))
        prefix_entry = ctk.CTkEntry(form, fg_color=COLORS.surface_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=36, placeholder_text="örn: work, art, cus")
        prefix_entry.pack(fill="x", pady=(0, 16))
        if tmpl: prefix_entry.insert(0, tmpl.prefix)

        # Multi-part editor (for multi mode)
        multi_frame = ctk.CTkFrame(form, fg_color=COLORS.surface_2, corner_radius=RADIUS.lg)
        multi_label = ctk.CTkLabel(multi_frame, text="Multi Mod Parçaları (GENİŞLİKxYÜKSEKLİK, virgülle)", font=make_font(TYPO.caption), text_color=COLORS.text_muted)
        multi_label.pack(anchor="w", padx=16, pady=(16, 8))

        multi_entry = ctk.CTkEntry(multi_frame, fg_color=COLORS.surface_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=36, placeholder_text="506x800, 100x800, 506x800")
        multi_entry.pack(fill="x", padx=16, pady=(0, 16))
        if tmpl and tmpl.mode == "multi" and isinstance(tmpl.parts, list):
            multi_entry.insert(0, ", ".join(f"{p.width}x{p.height}" for p in tmpl.parts))

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        dialog = form.master  # Toplevel
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)

        def save():
            # Build template
            mode_str = mode_var.get()
            mode = "uniform" if "Uniform" in mode_str else ("multi" if "Multi" in mode_str else "single")

            try:
                w = int(w_entry.get())
                h = int(h_entry.get())
                parts = int(parts_entry.get()) if parts_entry.get().isdigit() else 5
            except ValueError:
                messagebox.showerror("Hata", "Genişlik, yükseklik ve parça sayısı sayısal olmalı")
                return

            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Hata", "Şablon adı boş olamaz")
                return

            prefix = prefix_entry.get().strip() or "cus"

            if mode_var.get() == "Multi (farklı boyutlu parçalar)":
                # Parse multi parts
                parts_text = multi_entry.get().strip()
                parts = []
                for chunk in parts_text.split(","):
                    chunk = chunk.strip().lower().replace("×", "x")
                    if not chunk: continue
                    w_str, _, h_str = chunk.partition("x")
                    try:
                        parts.append({"width": int(w_str), "height": int(h_str)})
                    except:
                        pass
                if not parts:
                    messagebox.showerror("Hata", "En az bir parça girin")
                    return
                tmpl_new = Template(
                    name=name_entry.get().strip(),
                    mode="multi",
                    width=sum(p["width"] for p in parts),
                    height=max(p["height"] for p in parts),
                    parts=[{"width": p["width"], "height": p["height"]} for p in parts],
                    patch=patch_var.get(),
                    prefix=prefix_entry.get().strip() or "cus"
                )
            else:
                tmpl_new = Template(
                    name=name_entry.get().strip(),
                    mode="single" if "Single" in mode_var.get() else "uniform",
                    width=int(w_entry.get()),
                    height=int(h_entry.get()),
                    parts=int(parts_entry.get()) if parts_entry.get().isdigit() else 1,
                    patch=patch_var.get(),
                    prefix=prefix_entry.get().strip() or "cus"
                )

            # Check duplicate
            if any(t.name == tmpl_new.name for t in BUILTIN_TEMPLATES):
                messagebox.showerror("Hata", "Bu isimde şablon zaten var")
                return

            BUILTIN_TEMPLATES.append(tmpl_new)
            save_custom_presets()
            self.app.template = tmpl_new
            self.app._rebuild_template_cards()
            self._refresh_template_list()
            self.app._status.ok(f"Şablon {'güncellendi' if tmpl else 'oluşturuldu'}: {tmpl_new.name}")
            self._refresh_template_list()
            self._build_welcome()
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        AnimButton(btn_frame, text="İptal", nc=COLORS.surface_3, hc=COLORS.surface_4, height=36, command=dialog.destroy).pack(side="right", padx=8)
        AnimButton(btn_frame, text="Kaydet", variant="accent", height=36, text_color=COLORS.bg_0, command=save).pack(side="right", padx=8)

        dialog.transient(self)
        dialog.grab_set()
        dialog.wait_window()

    def _import_templates(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            count = 0
            for item in data:
                if not isinstance(item, dict): continue
                tmpl = Template(
                    name=item.get("name", "İçe Aktarılan"),
                    mode=item.get("mode", "uniform"),
                    width=item.get("width", 750),
                    height=item.get("height", 1250),
                    parts=item.get("parts", 5),
                    patch=item.get("patch", False),
                    prefix=item.get("prefix", "imp"),
                )
                if not any(t.name == tmpl.name for t in BUILTIN_TEMPLATES):
                    BUILTIN_TEMPLATES.append(tmpl)
                    count += 1
            save_custom_presets()
            self.app._rebuild_template_cards()
            self._refresh_template_list()
            self.app._status.ok(f"{count} şablon içe aktarıldı")
        except Exception as e:
            messagebox.showerror("Hata", f"İçe aktarma başarısız: {e}")

    def _export_templates(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            data = []
            for t in BUILTIN_TEMPLATES:
                if t.prefix in ("work", "art", "shot"):
                    continue
                data.append({
                    "name": t.name,
                    "mode": t.mode,
                    "width": t.width,
                    "height": t.height,
                    "parts": t.parts,
                    "patch": t.patch,
                    "prefix": t.prefix,
                })
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.app._status.ok(f"Şablonlar dışa aktarıldı: {path}")
        except Exception as e:
            messagebox.showerror("Hata", f"Dışa aktarma başarısız: {e}")

    def _import_templates(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            self._import_templates_from_path(path)

    def _export_templates(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            self._export_templates_to_path(path)

    # ══════════════════════════════════════════════════════════════════════
    # Preview Generation
    # ══════════════════════════════════════════════════════════════════════

    def _generate_template_preview(self, tmpl: Template) -> Image.Image:
        """Generate a preview image showing the template layout."""
        # Create a dummy source image
        src = Image.new("RGB", (tmpl.width * 2, tmpl.height), (50, 50, 60))
        draw = ImageDraw.Draw(src)
        for i in range(0, src.width, 40):
            draw.line([(i, 0), (i, src.height)], fill=(80, 80, 90))
        for i in range(0, src.height, 40):
            draw.line([(0, i), (src.width, i)], fill=(80, 80, 90))

        # Render preview
        preview = render_template_preview(src, tmpl, self.app._cfg, band_count=1)
        return preview.convert("RGB")

    def _build_welcome(self):
        for w in self._content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._content, text="🧩  Şablon Yönetimi", font=make_font(TYPO.display_md), text_color=COLORS.text_primary).pack(pady=(40, 8))
        ctk.CTkLabel(self._content, text="Şablonlarınızı oluşturun, düzenleyin ve yönetin.\nSoldaki listeden bir şablon seçin veya yeni bir tane oluşturun.",
                     font=make_font(TYPO.body_md), text_color=COLORS.text_muted, justify="center").pack(pady=(0, 24))

        AnimButton(self._content, text="+  Yeni Şablon Oluştur", variant="accent", height=44, text_color=COLORS.surface_0,
                   command=self._new_template).pack(pady=12)

        AnimButton(self._content, text="📥 Şablon İçe Aktar (JSON)", nc=COLORS.surface_3, hc=COLORS.surface_4, height=36,
                   command=self._import_templates).pack(pady=8)

        # Quick stats
        stats = ctk.CTkFrame(self._content, fg_color=COLORS.surface_2, corner_radius=RADIUS.lg)
        stats.pack(fill="x", padx=40, pady=(24, 0))

        ctk.CTkLabel(stats, text="📊  İstatistikler", font=make_font(TYPO.heading_sm, weight="bold"), text_color=COLORS.text_muted).pack(anchor="w", padx=16, pady=(16, 8))

        stats_grid = ctk.CTkFrame(stats, fg_color="transparent")
        stats_grid.pack(fill="x", padx=16, pady=(0, 16))
        stats_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        total = len(BUILTIN_TEMPLATES)
        builtin = sum(1 for t in BUILTIN_TEMPLATES if t.prefix in ("work", "art", "shot"))
        custom = total - builtin
        modes = set(t.mode for t in BUILTIN_TEMPLATES)

        for i, (label, value) in enumerate([
            ("Toplam", str(total)),
            ("Yerleşik", str(builtin)),
            ("Özel", str(custom)),
            ("Mod Sayısı", str(len(set(t.mode for t in BUILTIN_TEMPLATES)))),
        ]):
            card = ctk.CTkFrame(stats_grid, fg_color=COLORS.surface_3, corner_radius=RADIUS.md)
            card.grid(row=0, column=i, sticky="ew", padx=8, pady=8)
            ctk.CTkLabel(card, text=value, font=make_font(TYPO.display_md, weight="bold"), text_color=COLORS.accent_500).pack(pady=(12, 2))
            ctk.CTkLabel(card, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(pady=(0, 12))


# ═══════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════

__all__ = [
    "TemplateManagerPage",
]