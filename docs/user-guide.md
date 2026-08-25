# SplitForge User Guide

## Quick Start

1. **Download & Install**: Run `SplitForge_Setup_2.0.0.exe`
2. **Launch**: Start "SplitForge" from Start Menu
3. **Drag & Drop**: Drop an image onto the center area
4. **Select Template**: Choose from left sidebar (Workshop 5-part, Artwork 2-part, Screenshot)
5. **Click "✂ Böl"**: Split image into pieces
6. **Upload**: Click "🌐 Community Upload" to open Steam page

---

## Templates

| Template | Use Case | Parts | Dimensions |
|----------|----------|-------|------------|
| **Atölye Vitrini 5-Parça** | Workshop showcase | 5 vertical | 151×1250 each (754×1250 total) |
| **Çizim Vitrini 2-Parça** | Artwork showcase | 2 | 506×1000 + 100×1000 |
| **Ekran Görüntüsü** | Screenshots | 1 | 650×1000 |

---

## Interactive Preview

### Grid Controls
- **Drag**: Move the entire grid
- **Corner Handle**: Resize grid (hold Shift for 10px steps)
- **Double-click**: Instant split
- **Right-click**: Alignment menu (Center, Top, Bottom, Left, Right)

### Band Controls
- **Band Count** (top toolbar): Number of horizontal bands (1-20)
- Each band = one complete template set
- Perfect for tall images that need multiple Workshop rows

---

## Effects Panel (🎨 Efektler Button)

### 1. Auto-Crop (Ön İşleme)
Automatically removes transparent/solid-color borders before splitting.

### 2. Auto-Enhance (Otomatik İyileştir)
- **Intensity**: 0-100% contrast/saturation/sharpness boost
- Applied to entire canvas before splitting → seamless across pieces

### 3. Border FX (Kenarlık)
- **Template**: 10 built-in designs (neon, vhs, cinema, etc.)
- **Color**: Hex code (e.g., `#8B5CF6`)
- **Opacity**: 0-100%
- **Glow**: 0-100% outer glow effect

### 3. Text Overlay (Metin Katmanı)
- **Text**: Your title/signature
- **Position**: 7 presets + free drag in preview
- **Size**: 1-30% of height
- **Color**: Hex code
- **Opacity**: 0-100%

---

## Output Settings

| Setting | Options | Notes |
|---------|---------|-------|
| **Format** | PNG / JPG | PNG = lossless + patch; JPG = smaller |
| **JPG Quality** | 40-100 | Only for JPG |
| **GIF Lossy** | 0-200 | GIF compression (lower = better) |
| **GIF Colors** | 16-256 | Palette size |
| **Patch** | Auto | PNG last-byte = 0x21 (Steam hack) |

---

## Steam Upload

### Manual (Recommended)
1. Click **"🌐 Community Upload"**
2. Steam page opens in browser
3. Paste console snippet (F12 → Console)
4. Upload pieces in order
5. Set visibility

### Auto-Upload (Advanced)
1. Settings → **Auto-upload** ✓
2. Settings → **Auto-submit** ✓ (requires login)
3. Split → Auto-opens Steam → Uploads all

---

## Projects & Profiles

### Profiles (Settings → Profiles)
Save complete effect configurations:
- Border template + color + glow
- Text + position + style
- Enhance + auto-crop
- Upload settings

### Projects (Settings → Projects)
Save entire workflow state:
- Input files/folder
- Selected template
- Output folder
- Effects
- Steam upload URL + PublishedFileID
- Notes

**Use Case**: Switch between "Workshop Sword Mod" and "Artwork Showcase" instantly.

---

## GIF Maker (🎬 GIF / WebP Maker)

1. Tools → **GIF / WebP Maker**
2. Drop video (MP4, MOV, etc.)
3. Adjust:
   - **Preset**: Steam Fast / Steam Quality / WebP HD
   - **Width**: 480 / 720 / 1080
   - **FPS**: 5-60
   - **Lossy**: 0-200
   - **Effects**: 12 presets (Neon, VHS, Cinema, etc.)
4. **▶ Dönüştür** → Output in same folder

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open file |
| `Ctrl+Enter` | Split |
| `Esc` | Back / Close panel |
| `Mouse Wheel` | Zoom preview |
| `Drag` | Move grid |
| `Corner Drag` | Resize grid |
| `Right-click` | Alignment menu |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Drag-drop not working" | Run as Administrator once |
| "GIF not animating" | Install ffmpeg/gifsicle (bundled) |
| "Upload fails" | Check Steam login in browser |
| "Patch not applied" | Use PNG output, not JPG |
| "Grid invisible" | Image smaller than template → auto-crop or resize |

---

## Advanced Tips

### Perfect Workshop Grid
1. Source image: **754×1250** or **1508×2500** (exact multiples)
2. Template: **Atölye Vitrini 5-Parça**
3. Band count: 1 (single) or 2 (tall artwork)
2. Result: Pixel-perfect Steam grid

### Batch Processing
1. **Klasör Seç** → Select folder
2. **⚡ Toplu Böl** → Processes all images
3. Each file gets unique suffix (`_01`, `_02`)

### Custom Templates
Settings → **Şablonlar** → **YENİ ŞABLON OLUŞTUR**
- **Uniform**: Equal vertical slices
- **Multi**: Custom widths (e.g., `506x1000, 100x1000`)
- **Single**: One piece

---

## Support

- **GitHub Issues**: [github.com/aykut/steameditor/issues](https://github.com/aykut/steameditor/issues)
- **Discord**: [discord.gg/steameditor](https://discord.gg/steameditor)
- **Email**: aykut@steameditor.app

---

*SplitForge v2.0 — Made for Steam Creators*