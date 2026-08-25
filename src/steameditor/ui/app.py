"""steameditor.ui.app — Ana pencere montajı ve giriş noktası."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import BooleanVar, StringVar, colorchooser, filedialog, messagebox

import customtkinter as ctk

from steameditor.config import build_steam_upload_manifest
from steameditor.core import (
    list_border_templates,
    manual_crop_with_template,
    open_folder,
    process_image,
    split_gif_frames,
)
from steameditor.services import get_config_service
from steameditor.ui.app_shell import App as AppShell
from steameditor.ui.components import AnimButton
from steameditor.ui.design_system import COLORS, TYPO, apply_theme, make_font


class App(AppShell):
    """SplitForge ana penceresi — bölme, yükleme ve efekt işlemleri."""

    # ─── Batch Processing ────────────────────────────────────────────

    def _split_batch(self):
        """Gelişmiş toplu bölme: kuyruk, ilerleme çubuğu, hata yönetimi, iptal."""
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

        total = len(file_paths)
        template = self.template
        cfg = self._cfg
        outdir = self.output_dir
        self._splitting = True

        # Progress dialog
        dlg = ctk.CTkToplevel(self)
        dlg.title("İşleniyor")
        dlg.geometry("480x220")
        dlg.configure(fg_color=COLORS.surface_1)
        dlg.grab_set()
        dlg.resizable(False, False)

        ctk.CTkLabel(dlg, text="Toplu Bölme İşlemi",
                     font=make_font(TYPO.heading_md), text_color=COLORS.text_primary).pack(pady=(16, 4))

        lbl = ctk.CTkLabel(dlg, text="Hazırlanıyor...",
                           font=make_font(TYPO.body_md), text_color=COLORS.text_muted)
        lbl.pack()

        # Progress bar with percentage
        progress_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        progress_frame.pack(fill="x", padx=24, pady=8)
        bar = ctk.CTkProgressBar(progress_frame, width=420,
                                 progress_color=COLORS.accent_500,
                                 fg_color=COLORS.surface_3)
        bar.pack(fill="x", pady=4)
        bar.set(0)

        pct_label = ctk.CTkLabel(progress_frame, text="0%",
                                 font=make_font(TYPO.code, weight="bold"),
                                 text_color=COLORS.accent_500)
        pct_label.pack()

        # Current file label
        file_label = ctk.CTkLabel(dlg, text="Bekleniyor...",
                                  font=make_font(TYPO.caption), text_color=COLORS.text_muted)
        file_label.pack(pady=(0, 4))

        # Stats tracking
        stats_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=(0, 8))
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._batch_ok_lbl = ctk.CTkLabel(stats_frame, text="✓ 0",
                                          font=make_font(TYPO.caption, weight="bold"),
                                          text_color=COLORS.success)
        self._batch_ok_lbl.grid(row=0, column=0)
        self._batch_err_lbl = ctk.CTkLabel(stats_frame, text="✗ 0",
                                           font=make_font(TYPO.caption, weight="bold"),
                                           text_color=COLORS.error)
        self._batch_err_lbl.grid(row=0, column=1)
        self._batch_skip_lbl = ctk.CTkLabel(stats_frame, text="⊘ 0",
                                            font=make_font(TYPO.caption, weight="bold"),
                                            text_color=COLORS.warning)
        self._batch_skip_lbl.grid(row=0, column=2)

        # Cancel flag
        cancel_flag = threading.Event()

        def request_cancel():
            cancel_flag.set()
            cancel_btn.configure(state="disabled", text="İptal ediliyor...")
            self._status.set("İptal ediliyor... (mevcut dosya bitince durur)",
                             COLORS.warning, COLORS.warning, auto_reset=False)

        cancel_btn = AnimButton(dlg, text="İptal Et", height=32, text_color=COLORS.error,
                   font=make_font(TYPO.body_md), command=lambda: cancel_flag.set())
        cancel_btn.pack(fill="x", padx=24, pady=(4, 8))
        dlg.protocol("WM_DELETE_WINDOW", lambda: cancel_flag.set())

        created_count = [0]
        errors = []
        skipped = [0]
        renamed = []

        def worker():
            seen_stems = {}
            for i, path in enumerate(file_paths, 1):
                if cancel_flag.is_set():
                    break

                fname = os.path.basename(path)
                try:
                    # Duplicate stem handling
                    stem = os.path.splitext(os.path.basename(path))[0]
                    key = stem.lower()
                    count = seen_stems.get(key, 0)
                    seen_stems[key] = count + 1
                    override = stem if count == 0 else f"{stem}_{count + 1}"
                    if count > 0:
                        renamed.append(f"{fname} → {override}")

                    # Update UI
                    self.after(0, lambda i=i, total=total, f=fname: (
                        lbl.configure(text=f"{i}/{total} — {f}"),
                        bar.set(i / total),
                        pct_label.configure(text=f"{int(i/total*100)}%"),
                        file_label.configure(text=f),
                        self._batch_ok_lbl.configure(text=f"✓ {created_count[0]}"),
                        self._batch_err_lbl.configure(text=f"✗ {len(errors)}"),
                        self._batch_skip_lbl.configure(text=f"⊘ {skipped[0]}")
                    ))

                    # Process image
                    r = process_image(path, outdir, template, cfg, name_override=override)
                    if r:
                        created_count[0] += len(r)
                    else:
                        skipped[0] += 1

                    self.after(0, lambda: (
                        self._batch_ok_lbl.configure(text=f"✓ {created_count[0]}"),
                        self._batch_err_lbl.configure(text=f"✗ {len(errors)}"),
                        self._batch_skip_lbl.configure(text=f"⊘ {skipped[0]}")
                    ))

                except Exception as e:
                    errors.append(f"{os.path.basename(path)}: {e}")
                    self.after(0, lambda e=e: (
                        self._batch_err_lbl.configure(text=f"✗ {len(errors)}"),
                        self._status.set(f"Hata: {e}", COLORS.error, COLORS.error)
                    ))

            self.after(0, lambda: self._done_batch_dlg(
                dlg, total, created_count[0], errors, renamed, cancel_flag.is_set()))

        threading.Thread(target=worker, daemon=True).start()

    def _update_batch_stats(self, ok, err, skip):
        self._batch_ok_lbl.configure(text=f"✓ {ok}")
        self._batch_err_lbl.configure(text=f"✗ {err}")
        self._batch_skip_lbl.configure(text=f"⊘ {skip}")

    def _done_batch_dlg(self, dlg, total, created, errors, renamed, cancelled):
        self._splitting = False
        if dlg.winfo_exists():
            dlg.destroy()

        if cancelled:
            self._status.error(f"İptal edildi — {created} parça oluşturuldu")
        elif errors:
            self._status.error(f"{created} parça, {len(errors)} hata")
        else:
            self._status.ok(f"{created} parça oluşturuldu ✓")

        if created:
            self._show_split_preview(created)

        if self._cfg.get("open_output_after_process"):
            open_folder(self.output_dir)
        if self._cfg.get("auto_upload"):
            self._run_steam_community_upload(created)

        if errors or renamed:
            self._show_batch_report(total, created, errors, renamed)

    def _show_batch_report(self, total, created, errors, renamed):
        renamed = renamed or []
        win = ctk.CTkToplevel(self)
        win.title("Toplu İşlem Raporu")
        win.geometry("560x420")
        win.configure(fg_color=COLORS.surface_1)
        win.grab_set()

        ctk.CTkLabel(win, text="Toplu İşlem Raporu", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(pady=(16, 8))
        ctk.CTkLabel(win, text=f"Kaynak: {total} dosya · Çıktı: {len(created)} parça",
                     font=make_font(TYPO.body_md), text_color=COLORS.text_secondary).pack()

        if errors:
            ctk.CTkLabel(win, text="HATALAR:", font=make_font(TYPO.heading_sm, weight="bold"),
                         text_color=COLORS.error).pack(anchor="w", padx=20, pady=(12, 4))
            for e in errors:
                ctk.CTkLabel(win, text=f"  ✗ {e}", font=make_font(TYPO.caption),
                             text_color=COLORS.error, anchor="w").pack(anchor="w", padx=24)
        if renamed:
            ctk.CTkLabel(win, text="YENİDEN ADLANDIRILDI (çakışma önlendi):",
                         font=make_font(TYPO.heading_sm, weight="bold"),
                         text_color=COLORS.warning).pack(anchor="w", padx=20, pady=(12, 4))
            for r in renamed:
                ctk.CTkLabel(win, text=f"  ↻ {r}", font=make_font(TYPO.caption),
                             text_color=COLORS.warning, anchor="w").pack(anchor="w", padx=24)

        AnimButton(win, text="Tamam", variant="accent", height=36, command=win.destroy).pack(pady=20)

    # ─── Split Operations ────────────────────────────────────────────

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
        path = self.current_path
        template = self.template
        cfg = self._cfg
        outdir = self.output_dir
        grid_origin = self._grid_pos if self._pv else None
        grid_bands = self._pv["bands"] if self._pv else 1
        grid_scale = self._grid_scale if self._pv else 1.0
        self._splitting = True
        self._status.busy("Bölünüyor...")

        def worker():
            try:
                if grid_origin is not None and path.lower().endswith(".gif"):
                    created = split_gif_frames(path, outdir, template, cfg,
                        preset_origin=grid_origin, region_scale=grid_scale, band_count=grid_bands)
                elif grid_origin is not None:
                    created = manual_crop_with_template(self, path, outdir, template, cfg,
                        band_count=grid_bands, preset_origin=grid_origin, region_scale=grid_scale)
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

        if self._cfg.get("open_output_after_process"):
            open_folder(self.output_dir)
        if self._cfg.get("auto_upload"):
            self._run_steam_community_upload(created)

    def _show_split_preview(self, file_paths: list):
        self._last_outputs = list(file_paths)
        self._drop.grid_remove()
        self._split_prev.grid()
        parts = getattr(self.template, "parts", None)
        per_row = parts if isinstance(parts, int) and parts > 0 else min(5, max(1, len(file_paths)))
        self._split_prev.load(file_paths, parts_per_row=per_row)

    def _back_to_drop(self):
        self._split_prev.grid_remove()
        self._drop.grid()
        self._status.set("Hazır", COLORS.text_muted, COLORS.success, auto_reset=False)

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
            self._status.set(f"Klasör: {os.path.basename(p)}", COLORS.success, COLORS.success)

    def _pick_output_dir(self):
        p = filedialog.askdirectory()
        if p:
            self.output_dir = p
            if getattr(self, "_out_lbl", None):
                self._out_lbl.configure(text=self._short_path(p))
            self._cfg["output_dir"] = p
            get_config_service().save_config()
            self._status.set("Çıktı klasörü güncellendi", COLORS.success, COLORS.success)

    def _reset_zoom(self):
        if self._pv:
            self._pv["zoom"] = 1.0
            self._pv["focus"] = (0.5, 0.5)
            self._draw_grid_overlay()

    def _grid_release(self, _e=None):
        pv = self._pv
        if not pv:
            return
        press = pv.pop("press", None)
        if press and press[0] == "text":
            get_config_service().save_config()  # sürüklenen metin konumu kalıcı olsun

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

    # ─── Output Helpers ──────────────────────────────────────────────

    def _open_output_dir(self):
        open_folder(self.output_dir)

    def _open_file(self, path: str):
        try:
            if platform.system() == "Windows": os.startfile(path)
            else: webbrowser.open(path)
        except Exception as e:
            self._status.error(f"Açılamadı: {e}")

    def _copy_path(self, path: str):
        self.clipboard_clear()
        self.clipboard_append(path)
        self._status.set("Dosya yolu panoya kopyalandı", COLORS.success, COLORS.success)

    def _last_upload_paths(self):
        manifest = os.path.join(self.output_dir, "steam_upload_manifest.json")
        status_path = os.path.splitext(manifest)[0] + ".status.json"
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
        if not btn: return
        if self._has_resumable_upload():
            if not btn.winfo_ismapped(): btn.pack(fill="x", pady=2)
        else:
            if btn.winfo_ismapped(): btn.pack_forget()

    def _delete_output_file(self, path: str):
        try:
            if os.path.isfile(path): os.remove(path)
            self._last_outputs = [p for p in self._last_outputs if p != path]
            self._split_prev.load(self._last_outputs)
            self._status.ok("Dosya silindi")
        except Exception as e:
            self._status.error(f"Silinemedi: {e}")

    def _rerun_current(self):
        if self._batch_files: self._split_batch()
        elif not self.current_path: self._status.error("Yeniden işlemek için önce dosya veya klasör seç")
        elif os.path.isdir(self.current_path): self._split_batch()
        else: self._split_single()

    def _clear_outputs(self, file_paths: list):
        if not file_paths:
            self._status.error("Temizlenecek son çıktı yok")
            return
        if not messagebox.askyesno("Çıktıları Temizle", f"{len(file_paths)} çıktı dosyası silinecek. Devam edilsin mi?"):
            return
        removed = 0; errors = 0
        for path in file_paths:
            try:
                if os.path.isfile(path): os.remove(path); removed += 1
            except Exception: errors += 1
        self._last_outputs = []
        self._split_prev.load([])
        if errors: self._status.error(f"{removed} dosya silindi, {errors} hata")
        else: self._status.ok(f"{removed} çıktı temizlendi")

    # ─── Steam Community Upload ────────────────────────────────

    def _run_steam_community_upload(self, file_paths: list = None):
        if file_paths is None:
            file_paths = self._last_outputs
        if not file_paths:
            self._status.error("Yüklenecek çıktı yok. Önce 'Böl' yapın.")
            return
        if not self.output_dir:
            self._status.error("Çıktı klasörü ayarlanmamış")
            return
        manifest_path = build_steam_upload_manifest(file_paths, self._cfg, self.output_dir, self.template)
        self._run_uploader_subprocess(manifest_path)
        self._refresh_resume_upload_button()

    def _run_uploader_subprocess(self, manifest_path: str):
        if self._upload_proc and self._upload_proc.poll() is None:
            self._status.error("Zaten bir upload işlemi çalışıyor")
            return
        self._status.busy("Steam Community uploader başlatılıyor...")
        script = Path(__file__).parents[3] / "steam_community_uploader.py"
        if not script.exists():
            self._status.error(f"Uploader bulunamadı: {script.name}")
            return
        cmd = [sys.executable, str(script), "--manifest", manifest_path]
        self._upload_proc = subprocess.Popen(cmd, cwd=str(script.parent), creationflags=0)
        self._monitor_upload(manifest_path)

    def _monitor_upload(self, manifest_path: str):
        status_path = os.path.splitext(manifest_path)[0] + ".status.json"
        def check():
            if not os.path.exists(status_path):
                self.after(1000, lambda: self._monitor_upload(manifest_path))
                return
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    status = json.load(f)
            except Exception:
                self.after(1000, lambda: self._monitor_upload(manifest_path))
                return
            state = status.get("state", "")
            if state == "running":
                cur = status.get("current", 0)
                tot = status.get("total", 0)
                cur_file = status.get("current_file", "")
                self._status.set(f"Yükleniyor: {cur}/{tot} — {os.path.basename(cur_file)}",
                                 COLORS.accent, COLORS.accent, auto_reset=False)
                self.after(1000, lambda: self._monitor_upload(manifest_path))
            elif state == "done":
                self._status.ok("Tüm parçalar yüklendi ✓")
                self._notify_attention()
                self._refresh_resume_upload_button()
            elif state in ("failed", "error"):
                self._status.error(f"Upload hatası: {status.get('error', 'Bilinmeyen hata')}")
                self._refresh_resume_upload_button()
            else:
                self.after(1000, lambda: self._monitor_upload(manifest_path))
        self.after(1000, check)

    def _resume_steam_community_upload(self):
        manifest, _ = self._last_upload_paths()
        if os.path.exists(manifest):
            self._run_uploader_subprocess(manifest)
        else:
            self._status.error("Devam edilecek upload bulunamadı")

    # ─── External Tools ────────────────────────────────────────

    def _open_steam_artwork(self):
        webbrowser.open("https://steamcommunity.com/sharedfiles/edititem/767/3/")

    def _open_gif_maker(self):
        gif_maker = Path(__file__).parents[3] / "GIF" / "gif.py"
        if gif_maker.exists():
            subprocess.Popen([sys.executable, str(gif_maker)], cwd=str(gif_maker.parent), creationflags=0)
        else:
            self._status.error("GIF Maker bulunamadı (GIF/gif.py)")

    # ─── Effects Panel ────────────────────────────────────────

    def _toggle_effects_panel(self):
        if getattr(self, "_fx_open", False):
            if getattr(self, "_fx_panel", None):
                self._fx_panel.place_forget()
            self._fx_open = False
            return
        self._build_effects_panel()
        self._fx_panel.place(x=10, y=10, relheight=0.96)
        self._fx_panel.lift()
        self._fx_open = True

    def _build_effects_panel(self):
        if getattr(self, "_fx_panel", None):
            self._fx_panel.destroy()
        cfg = self._cfg
        panel = ctk.CTkScrollableFrame(self._drop, fg_color=COLORS.surface_1, corner_radius=12, width=300,
            scrollbar_button_color=COLORS.surface_4, scrollbar_button_hover_color=COLORS.accent_500)
        self._fx_panel = panel

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(head, text="🎨  Efektler", font=make_font(TYPO.heading_lg), text_color=COLORS.text_primary).pack(side="left", padx=4)
        AnimButton(head, text="✕", width=30, height=26, nc=COLORS.surface_3, hc=COLORS.surface_4,
                   text_color=COLORS.text_muted, command=lambda: panel.place_forget()).pack(side="right", padx=2)

        def live(_=None):
            get_config_service().save_config()
            if self.current_path and os.path.isfile(self.current_path):
                self._load_preview(self.current_path)

        def section(title):
            ctk.CTkLabel(panel, text=title, font=make_font(TYPO.heading_sm, weight="bold"),
                         text_color=COLORS.text_muted).pack(anchor="w", padx=6, pady=(10, 2))

        def enable_check(label, key):
            var = BooleanVar(value=bool(cfg.get(key, False)))
            def toggle():
                cfg[key] = bool(var.get())
                live()
            ctk.CTkCheckBox(panel, text=label, variable=var,
                            font=make_font(TYPO.body_md), text_color=COLORS.text_primary,
                            fg_color=COLORS.accent, hover_color=COLORS.accent_hover, checkmark_color=COLORS.bg_0,
                            command=toggle).pack(anchor="w", padx=6, pady=3)
            return var

        def slider_row(label, key, default, frm=0, to=100):
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=(0, 2))
            top = ctk.CTkFrame(row, fg_color="transparent"); top.pack(fill="x")
            ctk.CTkLabel(top, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(side="left")
            val = ctk.CTkLabel(top, text="", font=make_font(TYPO.code, weight="bold"), text_color=COLORS.accent_500)
            val.pack(side="right")
            s = ctk.CTkSlider(row, from_=frm, to=to, button_color=COLORS.accent_500,
                              button_hover_color=COLORS.accent_600, progress_color=COLORS.accent_500, fg_color=COLORS.surface_3)
            s.pack(fill="x")
            raw = cfg.get(key, default)
            s.set(int(raw) if raw is not None else default)
            def on(v):
                cfg[key] = int(float(v)); val.configure(text=str(int(float(v))))
                get_config_service().save_config(); live()
            s.configure(command=on); val.configure(text=str(int(s.get())))
            return s

        def color_entry(label, key, default):
            ctk.CTkLabel(panel, text=label, font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=6)
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=(0, 4))
            e = ctk.CTkEntry(row, fg_color=COLORS.surface_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=30)
            e.insert(0, cfg.get(key, default))
            e.pack(side="left", fill="x", expand=True)
            def commit(_=None):
                cfg[key] = e.get().strip() or default; live()
            e.bind("<FocusOut>", commit); e.bind("<Return>", commit)
            def pick():
                c = colorchooser.askcolor(color=cfg.get(key, default))[1]
                if c:
                    e.delete(0, "end"); e.insert(0, c); cfg[key] = c; live()
            AnimButton(row, text="🎨", width=34, height=30, nc=COLORS.surface_3, hc=COLORS.surface_4, command=pick).pack(side="left", padx=(4, 0))

        # ── ÖN İŞLEME ──
        section("ÖN İŞLEME")
        enable_check("Kenar boşluğunu otomatik kırp (autocrop)", "autocrop_enabled")

        # ── OTOMATİK İYİLEŞTİR ──
        section("OTOMATİK İYİLEŞTİR")
        enable_check("Kontrast/Doygunluk/Keskinlik dengele", "auto_enhance_enabled")
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
                              fg_color=COLORS.surface_3, button_color=COLORS.accent_500, button_hover_color=COLORS.accent_600,
                              dropdown_fg_color=COLORS.surface_3, dropdown_hover_color=COLORS.surface_4,
                              text_color=COLORS.text_primary).pack(fill="x", padx=6, pady=(0, 4))
            color_entry("Renk (#RRGGBB)", "border_fx_color", "#8B5CF6")
            slider_row("Opaklık", "border_fx_opacity", 100)
            slider_row("Glow", "border_fx_glow", 35)
        else:
            ctk.CTkLabel(panel, text="Border Templates klasöründe PNG yok.",
                         font=make_font(TYPO.caption), text_color=COLORS.error).pack(anchor="w", padx=6, pady=4)

        # ── METİN KATMANI ──
        section("METİN KATMANI")
        enable_check("Metin ekle", "text_overlay_enabled")
        ctk.CTkLabel(panel, text="Metin (önizlemede sürüklenebilir)", font=make_font(TYPO.caption), text_color=COLORS.text_muted).pack(anchor="w", padx=6)
        te = ctk.CTkEntry(panel, fg_color=COLORS.surface_3, border_color=COLORS.border_default, text_color=COLORS.text_primary, height=30, placeholder_text="Başlık / imza")
        te.insert(0, cfg.get("text_overlay_text", ""))
        te.pack(fill="x", padx=6, pady=(0, 4))
        def commit_text(_=None):
            cfg["text_overlay_text"] = te.get().strip(); live()
        te.bind("<FocusOut>", commit_text); te.bind("<Return>", commit_text)
        color_entry("Renk (#RRGGBB)", "text_overlay_color", "#FFFFFF")
        slider_row("Boyut", "text_overlay_size", 6, frm=1, to=30)
        slider_row("Opaklık", "text_overlay_opacity", 100)


# ══════════════════════════════════════════════════════════════════════
# MAIN ENTRY
# ══════════════════════════════════════════════════════════════════════

def main():
    apply_theme()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
