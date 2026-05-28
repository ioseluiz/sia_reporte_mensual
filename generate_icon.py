"""
Genera assets/icon.ico si no existe.
Ejecutar una vez antes de empaquetar, o reemplazar con tu propio icono .ico.
Requiere: pip install pillow
"""
import os
import sys

os.makedirs("assets", exist_ok=True)
output = os.path.join("assets", "icon.ico")

if os.path.exists(output):
    print(f"Icono ya existe: {output}")
    sys.exit(0)

from PIL import Image, ImageDraw, ImageFont

sizes = [256, 128, 64, 48, 32, 16]
images = []

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(2, size // 10)
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=size // 6,
        fill=(14, 71, 161, 255),
    )

    label = "SIA"
    font_size = max(8, size // 3)
    font = None
    for font_path in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
        label,
        fill=(255, 255, 255, 255),
        font=font,
    )
    images.append(img)

images[0].save(output, format="ICO", sizes=[(s, s) for s in sizes])
print(f"Icono generado: {output}")
