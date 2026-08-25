"""
steameditor.ui.border_editor — Custom border template editor.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk
from tkinter import filedialog, messagebox, colorchooser

from steameditor.ui.design_system import (
    COLORS, SPACING, TYPO, RADIUS, make_font, make_ctk_image, lerp_color
)
from steameditor.ui.components import AnimButton


class BorderTemplateEditor(ctk.CTkToplevel):
    """Editor for creating and editing border templates."""

    def __init__(self, master, template_path: Optional[Path] = None):
        super().__init__(master)
        self.title("Border Template Editor")
        self.geometry("1000x700")
        self.minsize(800, 600)
        self.configure(fg_color=COLORS.bg_1)

        self.template_path = template_path
        self.current_image: Optional[Image.Image] = None
        self.original_image: Optional[Image.Image] = None
        self.zoom = 1.0
        self.pan_offset = (0, 0)
        self.dragging = False
        self.drag_start = (0, 0)

        self._build_ui()

        if template_path and template_path.exists():
            self.load_template(template_path)
        else:
            self.new_template()

        self.transient(master)
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=COLORS.bg_2, height=50, corner_radius=0)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.grid_propagate(False)

        AnimButton(toolbar, text="📄 New", width=90, height=32,
                   command=self.new_template).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="📂 Open", width=90, height=32,
                   command=self.open_template).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="💾 Save", width=90, height=32,
                   variant="accent", command=self.save_template).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="💾 Save As", width=90, height=32,
                   command=self.save_template_as).pack(side="left", padx=6, pady=9)

        ctk.CTkLabel(toolbar, text="", width=20).pack(side="left")

        AnimButton(toolbar, text="🖼 Import Image", width=110, height=32,
                   command=self.import_image).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="🎨 Fill", width=90, height=32,
                   command=self.fill_canvas).pack(side="left", padx=6, pady=9)

        ctk.CTkLabel(toolbar, text="", width=20).pack(side="left")

        AnimButton(toolbar, text="🔍 Zoom In", width=90, height=32,
                   command=self.zoom_in).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="🔍 Zoom Out", width=90, height=32,
                   command=self.zoom_out).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="🔍 100%", width=90, height=32,
                   command=self.zoom_reset).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="🔍 Fit", width=90, height=32,
                   command=self.zoom_fit).pack(side="left", padx=6, pady=9)

        # Sidebar
        sidebar = ctk.CTkFrame(self, fg_color=COLORS.bg_2, width=260, corner_radius=0)
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sidebar, text="🎨 Tools", font=make_font(TYPO.heading_md),
                     text_color=COLORS.text_primary).pack(anchor="w", padx=16, pady=(16, 8))

        # Brush settings
        ctk.CTkLabel(sidebar, text="Brush", font=make_font(TYPO.body_md, weight="bold"),
                     text_color=COLORS.text_secondary).pack(anchor="w", padx=16, pady=(8, 4))

        brush_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brush_frame.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(brush_frame, text="Size:", font=make_font(TYPO.caption),
                     text_color=COLORS.text_muted).pack(side="left")
        self.brush_size = ctk.CTkSlider(brush_frame, from_=1, to=100, number_of_steps=99)
        self.brush_size.set(10)
        self.brush_size.pack(side="left", fill="x", expand=True, padx=8)
        self.brush_size_label = ctk.CTkLabel(brush_frame, text="10 px", font=make_font(TYPO.code),
                                             text_color=COLORS.accent, width=50)
        self.brush_size_label.pack(side="left")
        self.brush_size.configure(command=lambda v: self.brush_size_label.configure(text=f"{int(v)} px"))

        # Brush color
        color_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        color_frame.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(color_frame, text="Color:", font=make_font(TYPO.caption),
                     text_color=COLORS.text_muted).pack(side="left")
        self.brush_color = "#FFFFFF"
        self.color_btn = AnimButton(color_frame, text="", width=36, height=30,
                                    command=self.pick_brush_color)
        self.color_btn.configure(fg_color=self.brush_color)
        self.color_btn.pack(side="right", padx=4)

        # Opacity
        opacity_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        opacity_frame.pack(fill="x", padx=12, pady=(0, 16))
        ctk.CTkLabel(opacity_frame, text="Opacity:", font=make_font(TYPO.caption),
                     text_color=COLORS.text_muted).pack(side="left")
        self.brush_opacity = ctk.CTkSlider(opacity_frame, from_=0, to=100)
        self.brush_opacity.set(100)
        self.brush_opacity.pack(side="left", fill="x", expand=True, padx=8)
        self.opacity_label = ctk.CTkLabel(opacity_frame, text="100%", font=make_font(TYPO.code),
                                          text_color=COLORS.accent, width=50)
        self.opacity_label.pack(side="left")
        self.brush_opacity.configure(command=lambda v: self.opacity_label.configure(text=f"{int(v)}%"))

        # Layers
        ctk.CTkLabel(sidebar, text="Layers", font=make_font(TYPO.body_md, weight="bold"),
                     text_color=COLORS.text_secondary).pack(anchor="w", padx=16, pady=(8, 4))

        self.layers_list = ctk.CTkScrollableFrame(sidebar, fg_color=COLORS.bg_3, corner_radius=8)
        self.layers_list.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.layer_widgets = []

        layer_btns = ctk.CTkFrame(sidebar, fg_color="transparent")
        layer_btns.pack(fill="x", padx=12, pady=(0, 16))
        AnimButton(layer_btns, text="+ Add", width=60, height=28, variant="accent",
                   command=self.add_layer).pack(side="left", padx=2)
        AnimButton(layer_btns, text="🗑", width=36, height=28,
                   command=self.delete_layer).pack(side="left", padx=2)
        AnimButton(layer_btns, text="⬆", width=36, height=28,
                   command=self.move_layer_up).pack(side="left", padx=2)
        AnimButton(layer_btns, text="⬇", width=36, height=28,
                   command=self.move_layer_down).pack(side="left", padx=2)

        # Canvas
        self.canvas_frame = ctk.CTkFrame(self, fg_color=COLORS.bg_0, corner_radius=0)
        self.canvas_frame.grid(row=1, column=1, sticky="nsew", padx=1, pady=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        self.canvas = ctk.CTkCanvas(self.canvas_frame, bg=COLORS.bg_0, highlightthickness=0,
                                    cursor="crosshair")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Status bar
        self.status_bar = ctk.CTkFrame(self, fg_color=COLORS.bg_2, height=28, corner_radius=0)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_bar.grid_propagate(False)

        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready", font=make_font(TYPO.caption),
                                         text_color=COLORS.text_muted, anchor="w")
        self.status_label.pack(side="left", padx=12, pady=4)

        self.zoom_label = ctk.CTkLabel(self.status_bar, text="100%", font=make_font(TYPO.code),
                                       text_color=COLORS.accent, anchor="e")
        self.zoom_label.pack(side="right", padx=12, pady=4)

        self.add_layer()  # Initial layer

    # ─── Canvas Operations ───

    def on_canvas_configure(self, event):
        if self.current_image:
            self.render_canvas()

    def on_canvas_press(self, event):
        self.dragging = True
        self.drag_start = (event.x, event.y)
        self.last_pos = (event.x, event.y)

    def on_canvas_drag(self, event):
        if not self.dragging:
            return
        dx = event.x - self.last_pos[0]
        dy = event.y - self.last_pos[1]
        self.pan_offset = (self.pan_offset[0] + dx, self.pan_offset[1] + dy)
        self.last_pos = (event.x, event.y)
        self.render_canvas()

    def on_canvas_release(self, event):
        self.dragging = False

    def on_pan_start(self, event):
        self.pan_start = (event.x, event.y)
        self.pan_offset_start = self.pan_offset

    def on_pan_drag(self, event):
        dx = event.x - self.pan_start[0]
        dy = event.y - self.pan_start[1]
        self.pan_offset = (self.pan_offset_start[0] + dx, self.pan_offset_start[1] + dy)
        self.render_canvas()

    def on_mouse_wheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        self.zoom = min(5.0, self.zoom * 1.2)
        self.render_canvas()

    def zoom_out(self):
        self.zoom = max(0.1, self.zoom / 1.2)
        self.render_canvas()

    def zoom_reset(self):
        self.zoom = 1.0
        self.render_canvas()

    def zoom_fit(self):
        if not self.current_image:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        img_w, img_h = self.current_image.size
        scale = min(canvas_w / img_w, canvas_h / img_h) * 0.9
        self.zoom = max(0.1, min(5.0, scale))
        self.render_canvas()

    # ─── Layer Management ───

    def add_layer(self):
        layer_img = Image.new("RGBA", self.get_canvas_size(), (0, 0, 0, 0))
        layer = {"image": layer_img, "visible": True, "opacity": 1.0, "name": f"Layer {len(self.layer_widgets) + 1}"}
        self.layer_widgets.append(layer)
        self.create_layer_widget(layer, len(self.layer_widgets) - 1)
        self.render_canvas()
        self.set_status(f"Added layer: {layer['name']}")

    def delete_layer(self):
        if len(self.layer_widgets) <= 1:
            self.set_status("Cannot delete the last layer")
            return
        idx = self.get_selected_layer_index()
        if idx >= 0:
            layer = self.layer_widgets.pop(idx)
            self.rebuild_layer_widgets()
            self.render_canvas()
            self.set_status(f"Deleted layer: {layer['name']}")

    def move_layer_up(self):
        idx = self.get_selected_layer_index()
        if idx > 0:
            self.layer_widgets[idx], self.layer_widgets[idx - 1] = self.layer_widgets[idx - 1], self.layer_widgets[idx]
            self.rebuild_layer_widgets()
            self.render_canvas()

    def move_layer_down(self):
        idx = self.get_selected_layer_index()
        if idx < len(self.layer_widgets) - 1:
            self.layer_widgets[idx], self.layer_widgets[idx + 1] = self.layer_widgets[idx + 1], self.layer_widgets[idx]
            self.rebuild_layer_widgets()
            self.render_canvas()

    def get_selected_layer_index(self) -> int:
        for i, widget in enumerate(self.layer_widgets):
            if widget.get("selected", False):
                return i
        return len(self.layer_widgets) - 1

    def create_layer_widget(self, layer: dict, index: int):
        frame = ctk.CTkFrame(self.layers_list, fg_color=COLORS.bg_2, corner_radius=6)
        frame.pack(fill="x", padx=6, pady=3)
        frame.layer_index = index

        def on_click(e):
            self.select_layer(index)

        frame.bind("<Button-1>", on_click)
        for child in frame.winfo_children():
            child.bind("<Button-1>", on_click)

        # Visibility toggle
        vis_var = ctk.BooleanVar(value=layer["visible"])
        vis_cb = ctk.CTkCheckBox(frame, text="", variable=vis_var, width=24, height=24,
                                 command=lambda: self.toggle_layer_visibility(index, vis_var.get()))
        vis_cb.pack(side="left", padx=6, pady=6)
        layer["vis_var"] = vis_var

        # Name
        name_label = ctk.CTkLabel(frame, text=layer["name"], font=make_font(TYPO.body_sm),
                                  text_color=COLORS.text_primary, anchor="w")
        name_label.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        layer["name_widget"] = name_label

        # Opacity slider
        opacity_frame = ctk.CTkFrame(frame, fg_color="transparent")
        opacity_frame.pack(side="right", padx=8, pady=4)
        ctk.CTkLabel(opacity_frame, text="🌫", font=make_font(TYPO.caption)).pack(side="left")
        opacity_slider = ctk.CTkSlider(opacity_frame, from_=0, to=100, width=80)
        opacity_slider.set(int(layer["opacity"] * 100))
        opacity_slider.pack(side="left", padx=4)
        opacity_slider.configure(command=lambda v: self.set_layer_opacity(index, v / 100))
        layer["opacity_slider"] = opacity_slider

        widget_data = {"frame": frame, "layer": layer, "selected": False}
        self.layer_widgets.append(widget_data)

    def rebuild_layer_widgets(self):
        for widget in self.layer_widgets:
            widget["frame"].destroy()
        self.layer_widgets.clear()
        for i, layer in enumerate(self.current_layers):
            self.create_layer_widget(layer, i)

    def select_layer(self, index: int):
        for widget in self.layer_widgets:
            widget["selected"] = False
            widget["frame"].configure(fg_color=COLORS.bg_2)
        self.layer_widgets[index]["selected"] = True
        self.layer_widgets[index]["frame"].configure(fg_color=COLORS.accent_dim)

    def toggle_layer_visibility(self, index: int, visible: bool):
        self.current_layers[index]["visible"] = visible
        self.render_canvas()

    def set_layer_opacity(self, index: int, opacity: float):
        self.current_layers[index]["opacity"] = opacity
        self.render_canvas()

    @property
    def current_layers(self) -> list:
        return [w["layer"] for w in self.layer_widgets]

    # ─── Template Operations ───

    def get_canvas_size(self) -> tuple[int, int]:
        if self.current_image:
            return self.current_image.size
        return (800, 1200)  # Default template size

    def new_template(self):
        size = (800, 1200)  # Default Steam showcase size
        self.current_image = Image.new("RGBA", size, (0, 0, 0, 0))
        self.original_image = self.current_image.copy()
        self.layer_widgets = []
        self.add_layer()
        self.zoom = 1.0
        self.pan_offset = (0, 0)
        self.template_path = None
        self.render_canvas()
        self.set_status("New template created")

    def load_template(self, path: Path):
        try:
            self.current_image = Image.open(path).convert("RGBA")
            self.original_image = self.current_image.copy()
            self.template_path = path
            self.layer_widgets = []
            self.add_layer()  # Base layer with template
            self.current_layers[0]["image"] = self.current_image
            self.zoom = 1.0
            self.pan_offset = (0, 0)
            self.render_canvas()
            self.set_status(f"Loaded: {path.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {e}")

    def open_template(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")],
            title="Open Border Template"
        )
        if path:
            self.load_template(Path(path))

    def save_template(self):
        if self.template_path:
            self.save_template_as_path(self.template_path)
        else:
            self.save_template_as()

    def save_template_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All files", "*.*")],
            title="Save Template As"
        )
        if path:
            self.save_template_as_path(Path(path))

    def save_template_as_path(self, path: Path):
        try:
            # Flatten layers
            result = self.flatten_layers()
            result.save(path, "PNG")
            self.template_path = path
            self.set_status(f"Saved: {path.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def import_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")],
            title="Import Image"
        )
        if path:
            try:
                img = Image.open(path).convert("RGBA")
                # Add as new layer
                layer_img = Image.new("RGBA", self.get_canvas_size(), (0, 0, 0, 0))
                # Center the imported image
                x = (self.get_canvas_size()[0] - img.width) // 2
                y = (self.get_canvas_size()[1] - img.height) // 2
                layer_img.paste(img, (x, y), img)
                layer = {"image": layer_img, "visible": True, "opacity": 1.0, "name": f"Imported: {Path(path).name}"}
                self.layer_widgets.append(layer)
                self.create_layer_widget(layer, len(self.layer_widgets) - 1)
                self.render_canvas()
                self.set_status(f"Imported: {Path(path).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import: {e}")

    def fill_canvas(self):
        color = colorchooser.askcolor(initialcolor=self.brush_color)[1]
        if color:
            hex_color = color
            # Convert to RGBA
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            layer = self.current_layers[self.get_selected_layer_index()]
            draw = ImageDraw.Draw(layer["image"])
            draw.rectangle([0, 0, *self.get_canvas_size()], fill=(r, g, b, 255))
            self.render_canvas()
            self.set_status(f"Filled with {hex_color}")

    def pick_brush_color(self):
        color = colorchooser.askcolor(initialcolor=self.brush_color)[1]
        if color:
            self.brush_color = color
            self.color_btn.configure(fg_color=color)

    # ─── Rendering ───

    def flatten_layers(self) -> Image.Image:
        """Flatten all visible layers into a single image."""
        canvas_size = self.get_canvas_size()
        result = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        for layer in self.current_layers:
            if not layer["visible"]:
                continue
            opacity = int(layer["opacity"] * 255)
            layer_img = layer["image"].copy()
            if opacity < 255:
                alpha = layer_img.split()[3]
                alpha = alpha.point(lambda a: int(a * opacity / 255))
                layer_img.putalpha(alpha)
            result = Image.alpha_composite(result, layer_img)
        return result

    def render_canvas(self):
        if not self.current_image:
            return

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())

        # Flatten visible layers
        display_img = self.flatten_layers()

        # Apply zoom and pan
        w, h = display_img.size
        disp_w = int(w * self.zoom)
        disp_h = int(h * self.zoom)

        if disp_w > 0 and disp_h > 0:
            display_img = display_img.resize((disp_w, disp_h), Image.LANCZOS)

        # Create canvas image with pan
        canvas_img = Image.new("RGBA", (canvas_w, canvas_h), COLORS.bg_0)
        px = self.pan_offset[0] + (canvas_w - disp_w) // 2
        py = self.pan_offset[1] + (canvas_h - disp_h) // 2
        canvas_img.paste(display_img, (px, py), display_img)

        # Draw grid overlay if zoomed in
        if self.zoom > 0.5:
            draw = ImageDraw.Draw(canvas_img)
            grid_size = int(50 * self.zoom)
            for x in range(px % grid_size, canvas_w, grid_size):
                draw.line([(x, 0), (x, canvas_h)], fill=(255, 255, 255, 20), width=1)
            for y in range(py % grid_size, canvas_h, grid_size):
                draw.line([(0, y), (canvas_w, y)], fill=(255, 255, 255, 20), width=1)

        # Update canvas
        self.tk_image = make_ctk_image(canvas_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        self.zoom_label.configure(text=f"{int(self.zoom * 100)}%")

    def set_status(self, msg: str):
        self.status_label.configure(text=msg)


# ─── Color Palette Manager ───

class ColorPaletteManager(ctk.CTkToplevel):
    """Manager for creating and organizing color palettes."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Color Palette Manager")
        self.geometry("600x500")
        self.minsize(500, 400)
        self.configure(fg_color=COLORS.bg_1)

        self.palettes: dict[str, list[str]] = self.load_palettes()
        self.current_palette: Optional[str] = None

        self._build_ui()
        self.refresh_list()

        self.transient(master)
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=COLORS.bg_2, height=50, corner_radius=0)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.grid_propagate(False)

        AnimButton(toolbar, text="+ New", width=90, height=32, variant="accent",
                   command=self.new_palette).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="📂 Import", width=90, height=32,
                   command=self.import_palette).pack(side="left", padx=6, pady=9)
        AnimButton(toolbar, text="📤 Export", width=90, height=32,
                   command=self.export_palette).pack(side="left", padx=6, pady=9)

        # Left: palette list
        list_frame = ctk.CTkFrame(self, fg_color=COLORS.bg_2, corner_radius=0, width=200)
        list_frame.grid(row=1, column=0, sticky="nsw", padx=(1, 0), pady=1)
        list_frame.grid_propagate(False)

        ctk.CTkLabel(list_frame, text="Palettes", font=make_font(TYPO.heading_md),
                     text_color=COLORS.text_primary).pack(anchor="w", padx=12, pady=12)

        self.listbox = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # Right: palette editor
        self.editor_frame = ctk.CTkFrame(self, fg_color=COLORS.bg_1, corner_radius=0)
        self.editor_frame.grid(row=1, column=1, sticky="nsew")
        self.editor_frame.grid_columnconfigure(0, weight=1)

        self.editor_label = ctk.CTkLabel(self.editor_frame, text="Select a palette to edit",
                                         font=make_font(TYPO.heading_md), text_color=COLORS.text_muted)
        self.editor_label.pack(expand=True)

    def refresh_list(self):
        for widget in self.listbox.winfo_children():
            widget.destroy()

        for name in sorted(self.palettes.keys()):
            btn = ctk.CTkButton(self.listbox, text=name, anchor="w",
                                fg_color=COLORS.bg_3 if self.current_palette == name else "transparent",
                                hover_color=COLORS.bg_4,
                                text_color=COLORS.text_primary,
                                command=lambda n=name: self.select_palette(n))
            btn.pack(fill="x", padx=8, pady=2)

    def select_palette(self, name: str):
        self.current_palette = name
        self.refresh_list()
        self.show_editor(name)

    def show_editor(self, name: str):
        for widget in self.editor_frame.winfo_children():
            widget.destroy()

        colors = self.palettes.get(name, [])

        ctk.CTkLabel(self.editor_frame, text=f"Editing: {name}",
                     font=make_font(TYPO.heading_md), text_color=COLORS.text_primary).pack(anchor="w", padx=16, pady=(16, 8))

        # Color grid
        grid_frame = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        grid_frame.pack(fill="x", padx=16, pady=(0, 8))
        grid_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        for i, color in enumerate(colors):
            row = i // 5
            col = i % 5
            btn = ctk.CTkButton(grid_frame, text="", fg_color=color, hover_color=color,
                                width=60, height=40, corner_radius=8,
                                command=lambda c=color, idx=i: self.edit_color(name, idx, c))
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="ew")

        # Add color button
        add_btn = AnimButton(grid_frame, text="+ Add Color", width=60, height=40,
                             command=lambda: self.add_color(name))
        row = len(colors) // 5
        col = len(colors) % 5
        add_btn.grid(row=row, column=col, padx=4, pady=4, sticky="ew")

        # Actions
        actions = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(8, 16))
        AnimButton(actions, text="🗑 Remove Selected", width=140, height=32,
                   text_color=COLORS.error, command=lambda: self.remove_selected(name)).pack(side="left", padx=4)
        AnimButton(actions, text="💾 Save", width=90, height=32, variant="accent",
                   command=lambda: self.save_palettes()).pack(side="right", padx=4)

    def edit_color(self, palette_name: str, index: int, current_color: str):
        color = colorchooser.askcolor(initialcolor=current_color)[1]
        if color:
            self.palettes[palette_name][index] = color
            self.show_editor(palette_name)

    def add_color(self, name: str):
        color = colorchooser.askcolor(initialcolor="#FFFFFF")[1]
        if color:
            self.palettes[name].append(color)
            self.show_editor(name)

    def remove_selected(self, name: str):
        # In a real implementation, track selection
        if self.palettes[name]:
            self.palettes[name].pop()
            self.show_editor(name)

    def new_palette(self):
        name = ctk.CTkInputDialog(text="Palette name:", title="New Palette").get_input()
        if name:
            self.palettes[name] = ["#FFFFFF", "#000000", "#FF0000", "#00FF00", "#0000FF"]
            self.select_palette(name)
            self.save_palettes()

    def import_palette(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            try:
                import json
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.palettes.update(data)
                elif isinstance(data, list):
                    self.palettes[f"Imported {len(self.palettes) + 1}"] = data
                self.refresh_list()
                self.save_palettes()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import: {e}")

    def export_palette(self):
        if not self.current_palette:
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                             filetypes=[("JSON", "*.json")])
        if path:
            try:
                import json
                data = {self.current_palette: self.palettes[self.current_palette]}
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

    def load_palettes(self) -> dict[str, list[str]]:
        config_dir = Path.home() / "AppData" / "Local" / "SplitForge"
        config_dir.mkdir(parents=True, exist_ok=True)
        palette_file = config_dir / "palettes.json"
        if palette_file.exists():
            try:
                import json
                return json.loads(palette_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "Default": ["#FFFFFF", "#000000", "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFBE0B", "#FB5607", "#8338EC", "#3A86FF"],
            "Steam": ["#1B2838", "#2A475E", "#66C0F4", "#C7D5E0", "#AC3B61", "#F0F0F0"],
            "Cyberpunk": ["#0D0D0D", "#FF00FF", "#00FFFF", "#FFFF00", "#FF206E", "#00FF88"],
            "Pastel": ["#FFD1DC", "#C7CEEA", "#B5EAD7", "#FFE5B4", "#FFB7CE", "#A0E7E5"],
        }

    def save_palettes(self):
        config_dir = Path.home() / "AppData" / "Local" / "SplitForge"
        config_dir.mkdir(parents=True, exist_ok=True)
        palette_file = config_dir / "palettes.json"
        import json
        palette_file.write_text(json.dumps(self.palettes, indent=2), encoding="utf-8")



# ─── Animation Timeline (for GIF Maker) ───

class AnimationTimeline(ctk.CTkFrame):
    """Timeline editor for GIF/WebP animation."""

    def __init__(self, master, on_frame_change=None, on_duration_change=None):
        super().__init__(master, fg_color=COLORS.bg_2, corner_radius=8)
        self.on_frame_change = on_frame_change
        self.on_duration_change = on_duration_change
        self.frames: list[dict] = []  # {image, duration, delay}
        self.current_frame = 0
        self.playing = False
        self.duration = 100  # ms per frame default

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=40)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

        AnimButton(toolbar, text="⏮", width=36, height=32,
                   command=self.first_frame).pack(side="left", padx=2)
        AnimButton(toolbar, text="⏪", width=36, height=32,
                   command=self.prev_frame).pack(side="left", padx=2)
        self.play_btn = AnimButton(toolbar, text="▶", width=36, height=32, variant="accent",
                                   command=self.toggle_play)
        self.play_btn.pack(side="left", padx=2)
        AnimButton(toolbar, text="⏩", width=36, height=32,
                   command=self.next_frame).pack(side="left", padx=2)
        AnimButton(toolbar, text="⏭", width=36, height=32,
                   command=self.last_frame).pack(side="left", padx=2)

        ctk.CTkLabel(toolbar, text="", width=20).pack(side="left")

        AnimButton(toolbar, text="+ Add Frame", width=100, height=32,
                   command=self.add_frame).pack(side="left", padx=4)
        AnimButton(toolbar, text="🗑 Delete", width=100, height=32,
                   text_color=COLORS.error, command=self.delete_frame).pack(side="left", padx=4)

        ctk.CTkLabel(toolbar, text="", width=20).pack(side="left")

        ctk.CTkLabel(toolbar, text="Duration (ms):", font=make_font(TYPO.caption),
                     text_color=COLORS.text_muted).pack(side="left", padx=(16, 4))
        self.duration_entry = ctk.CTkEntry(toolbar, width=60, height=28, justify="center")
        self.duration_entry.insert(0, "100")
        self.duration_entry.pack(side="left", padx=4)
        self.duration_entry.bind("<Return>", lambda e: self.update_duration())
        AnimButton(toolbar, text="Apply", width=60, height=28,
                   command=self.update_duration).pack(side="left", padx=4)

        # Timeline scrubber
        scrubber_frame = ctk.CTkFrame(self, fg_color=COLORS.bg_3, corner_radius=8, height=80)
        scrubber_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        scrubber_frame.grid_propagate(False)
        scrubber_frame.grid_columnconfigure(0, weight=1)

        self.scrubber_canvas = ctk.CTkCanvas(scrubber_frame, bg=COLORS.bg_0, highlightthickness=0,
                                              height=60, cursor="hand2")
        self.scrubber_canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.scrubber_canvas.bind("<Button-1>", self.on_scrubber_click)
        self.scrubber_canvas.bind("<B1-Motion>", self.on_scrubber_drag)
        self.scrubber_canvas.bind("<Configure>", lambda e: self.draw_scrubber())

    def set_frames(self, frames: list[dict]):
        """frames: list of {image: PIL.Image, duration: int}"""
        self.frames = frames
        self.current_frame = 0
        self.draw_scrubber()
        self.update_frame_display()

    def add_frame(self):
        if not self.frames:
            return
        # Duplicate current frame
        new_frame = {
            "image": self.frames[self.current_frame]["image"].copy(),
            "duration": self.frames[self.current_frame]["duration"]
        }
        self.frames.insert(self.current_frame + 1, new_frame)
        self.current_frame += 1
        self.draw_scrubber()
        self.update_frame_display()

    def delete_frame(self):
        if len(self.frames) <= 1:
            return
        self.frames.pop(self.current_frame)
        if self.current_frame >= len(self.frames):
            self.current_frame = len(self.frames) - 1
        self.draw_scrubber()
        self.update_frame_display()

    def first_frame(self):
        self.current_frame = 0
        self.update_frame_display()

    def last_frame(self):
        self.current_frame = len(self.frames) - 1
        self.update_frame_display()

    def prev_frame(self):
        self.current_frame = max(0, self.current_frame - 1)
        self.update_frame_display()

    def next_frame(self):
        self.current_frame = min(len(self.frames) - 1, self.current_frame + 1)
        self.update_frame_display()

    def toggle_play(self):
        self.playing = not self.playing
        self.play_btn.configure(text="⏸" if self.playing else "▶")
        if self.playing:
            self.animate()

    def animate(self):
        if not self.playing:
            return
        self.next_frame()
        self.after(self.frames[self.current_frame]["duration"], self.animate)

    def on_scrubber_click(self, event):
        self.scrub_to_position(event.x)

    def on_scrubber_drag(self, event):
        self.scrub_to_position(event.x)

    def scrub_to_position(self, x: int):
        canvas_w = self.scrubber_canvas.winfo_width()
        if canvas_w > 0 and self.frames:
            frame = int((x / canvas_w) * len(self.frames))
            frame = max(0, min(len(self.frames) - 1, frame))
            if frame != self.current_frame:
                self.current_frame = frame
                self.update_frame_display()

    def draw_scrubber(self):
        self.scrubber_canvas.delete("all")
        if not self.frames:
            return

        w = self.scrubber_canvas.winfo_width()
        h = self.scrubber_canvas.winfo_height()
        if w <= 1:
            return

        frame_w = w / len(self.frames)

        # Draw frames
        for i, frame in enumerate(self.frames):
            x = i * frame_w
            color = COLORS.accent if i == self.current_frame else COLORS.bg_4
            self.scrubber_canvas.create_rectangle(x, 0, x + frame_w, h, fill=color, outline="")

            # Duration indicator
            duration = frame.get("duration", 100)
            if duration > 100:
                self.scrubber_canvas.create_line(x + frame_w * 0.5, h * 0.8, x + frame_w * 0.5, h,
                                                 fill=COLORS.accent, width=2)

        # Current time marker
        if self.current_frame < len(self.frames):
            x = (self.current_frame + 0.5) * frame_w
            self.scrubber_canvas.create_line(x, 0, x, h, fill=COLORS.accent, width=2, dash=(4, 4))

    def update_frame_display(self):
        if self.on_frame_change and self.frames:
            self.on_frame_change(self.current_frame, self.frames[self.current_frame])

    def update_duration(self):
        try:
            duration = int(self.duration_entry.get())
            if 10 <= duration <= 10000:
                self.frames[self.current_frame]["duration"] = duration
                if self.on_duration_change:
                    self.on_duration_change(self.current_frame, duration)
                self.draw_scrubber()
        except ValueError:
            pass


# ─── Export ───

__all__ = [
    "PluginBase",
    "EffectPlugin",
    "TemplatePlugin",
    "ExportPlugin",
    "PluginMetadata",
    "PluginManager",
    "get_plugin_manager",
    "BuiltinEffectPlugin",
    "BorderTemplateEditor",
    "ColorPaletteManager",
    "AnimationTimeline",
    "create_plugin_template",
    "write_plugin_template",
]