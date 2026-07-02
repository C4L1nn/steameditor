"""make_icon.py — SplitForge uygulama ikonu üretir (makas + bölme grid'i).

Çalıştır: python make_icon.py
Üretir: app_icon.ico (çok boyutlu) + app_icon.png (256px, iconphoto için).
Bağımlılık sadece Pillow; tekrar üretilebilir olsun diye repoda tutulur.
"""
import os
from PIL import Image, ImageDraw, ImageFont

ORANGE = (249, 115, 22, 255)
ORANGE_DIM = (249, 115, 22, 70)
BG0 = (13, 13, 13, 255)
BG1 = (28, 28, 30, 255)
SIZE = 512  # yüksek çözünürlükte çiz, sonra küçült


def _scissors_font(px):
    for path in (r"C:\Windows\Fonts\seguisym.ttf",   # Segoe UI Symbol (monokrom ✂)
                 r"C:\Windows\Fonts\SEGUISYM.TTF",
                 r"C:\Windows\Fonts\DejaVuSans.ttf"):
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, px)
            except Exception:
                continue
    return None


def draw_scissors_manual(d, cx, cy, r):
    """Font'ta makas glifi yoksa elle çiz: iki halka + çapraz iki bıçak."""
    ring = int(r * 0.34)
    lw = max(6, int(r * 0.14))
    # Halkalar (alt sol / alt sağ)
    d.ellipse((cx - r*0.75 - ring, cy + r*0.35 - ring, cx - r*0.75 + ring, cy + r*0.35 + ring),
              outline=ORANGE, width=lw)
    d.ellipse((cx + r*0.10 - ring, cy + r*0.55 - ring, cx + r*0.10 + ring, cy + r*0.55 + ring),
              outline=ORANGE, width=lw)
    # Bıçaklar (halkalardan üste doğru çaprazlanır)
    pivot = (cx - r*0.05, cy - r*0.05)
    d.line((cx - r*0.75, cy + r*0.35, cx + r*0.55, cy - r*0.85), fill=ORANGE, width=lw)
    d.line((cx + r*0.10, cy + r*0.55, cx - r*0.65, cy - r*0.85), fill=ORANGE, width=lw)
    # Pivot vidası
    d.ellipse((pivot[0]-lw, pivot[1]-lw, pivot[0]+lw, pivot[1]+lw), fill=(8, 8, 8, 255))


def build(size=SIZE):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(size * 0.06)
    # Yuvarlak koyu kare zemin + ince turuncu çerçeve
    d.rounded_rectangle((m, m, size - m, size - m), radius=int(size * 0.20),
                        fill=BG1, outline=ORANGE, width=max(3, int(size * 0.018)))
    # Arka planda 5'li dikey bölme grid'i (vitrini temsil eder)
    inset = int(size * 0.16)
    top, bot = inset, size - inset
    for i in range(1, 5):
        x = inset + (size - 2 * inset) * i / 5
        d.line((x, top, x, bot), fill=ORANGE_DIM, width=max(2, int(size * 0.012)))
    d.rounded_rectangle((inset, top, size - inset, bot), radius=int(size*0.05),
                        outline=ORANGE_DIM, width=max(2, int(size * 0.010)))
    # Makas — önce font glifini dene, olmazsa elle çiz
    font = _scissors_font(int(size * 0.62))
    drawn = False
    if font is not None:
        try:
            bbox = d.textbbox((0, 0), "✂", font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            # gölge + turuncu
            pos = ((size - tw)//2 - bbox[0], (size - th)//2 - bbox[1])
            d.text((pos[0]+4, pos[1]+4), "✂", font=font, fill=(0, 0, 0, 160))
            d.text(pos, "✂", font=font, fill=ORANGE)
            drawn = True
        except Exception:
            drawn = False
    if not drawn:
        draw_scissors_manual(d, size/2, size/2, size*0.30)
    return img


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    master = build(SIZE)
    png = master.resize((256, 256), Image.LANCZOS)
    png.save(os.path.join(root, "app_icon.png"))
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(os.path.join(root, "app_icon.ico"), sizes=sizes)
    print("app_icon.ico + app_icon.png üretildi")


if __name__ == "__main__":
    main()
