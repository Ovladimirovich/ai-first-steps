#!/usr/bin/env python3
"""
Готовит спрайты персонажей для build_ffmpeg_video.py из «сырых» картинок.

Что делает:
  1. убирает белый фон (flood fill от краёв + допуск по светлоте, с мягким краем по альфе)
  2. обрезает по содержимому
  3. вписывает фигуру в 400x400 PNG с прозрачным фоном (низ фигуры = низ картинки)
  4. пишет assets/pixar/<who>.png + <who>_<emotion>.png

«Сырые» картинки лежат в assets/pixar/raw/_raw_<who>_<emotion>.jpg
(или рядом, в assets/pixar/) — скрипт ищет в обоих местах.

usage:
  python tools/prepare_pixar_sprites.py              # все *_raw_*.png -> спрайты
  python tools/prepare_pixar_sprites.py --size 480   # другой размер холста
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "pixar"

# (raw file, out file)
MAPPING = [
    ("_raw_bit_neutral.png",    "bit.png"),
    ("_raw_bit_surprised.png",  "bit_surprised.png"),
    ("_raw_bit_happy.png",      "bit_happy.png"),
    ("_raw_masha_neutral.png",  "masha.png"),
    ("_raw_masha_surprised.png", "masha_surprised.png"),
    ("_raw_masha_happy.png",    "masha_happy.png"),
]


def cut_white_bg(img, tol=28, feather=46):
    """Убирает почти-белый фон: считаем «фоном» пиксели, близкие к белому,
    и оставляем только ту область, которая связана с краем (флуд-филл),
    чтобы белые блики внутри персонажа не вырезались."""
    from PIL import Image, ImageFilter
    import numpy as np

    rgb = np.asarray(img.convert("RGB")).astype(np.int16)
    h, w, _ = rgb.shape
    # «белизна»: минимальный канал высокий и разброс между каналами маленький
    mn = rgb.min(axis=2)
    mx = rgb.max(axis=2)
    near_white = (mn >= 255 - tol) & ((mx - mn) <= 26)

    # флуд-филл от рамки по near_white — только внешний фон
    mask = np.zeros((h, w), dtype=bool)
    stack = []
    for x in range(w):
        for y in (0, h - 1):
            if near_white[y, x] and not mask[y, x]:
                mask[y, x] = True
                stack.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if near_white[y, x] and not mask[y, x]:
                mask[y, x] = True
                stack.append((y, x))
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and near_white[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                stack.append((ny, nx))

    alpha = np.where(mask, 0, 255).astype(np.uint8)
    a_img = Image.fromarray(alpha, "L")
    # мягкий край: чуть размыть альфу и подрезать полупрозрачную кайму
    a_img = a_img.filter(ImageFilter.GaussianBlur(1.6))
    a_img = a_img.point(lambda v: 0 if v < 40 else (255 if v > 210 else int(v * 1.15)))

    out = img.convert("RGBA")
    out.putalpha(a_img)
    # срезаем «светящуюся» кайму вокруг фигуры: чуть эрозия альфы
    return out


def trim(img, pad=6):
    """Обрезка по непрозрачным пикселям."""
    bbox = img.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(img.width, x1 + pad); y1 = min(img.height, y1 + pad)
    return img.crop((x0, y0, x1, y1))


def fit_canvas(img, size=400, bottom_margin=6):
    """Вписывает фигуру в квадрат size x size, низ фигуры у нижнего края."""
    from PIL import Image
    w, h = img.size
    scale = min(size / w, (size - bottom_margin) / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    small = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(small, ((size - nw) // 2, size - bottom_margin - nh))
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=400, help="сторона холста PNG")
    args = ap.parse_args()

    from PIL import Image
    if not ASSETS.exists():
        print(f"нет папки {ASSETS}", file=sys.stderr); return 1
    done = 0
    for raw_name, out_name in MAPPING:
        # «сырьё» ищем рядом и в assets/pixar/raw/, в PNG или JPEG
        cands = [ASSETS / raw_name, ASSETS / "raw" / raw_name,
                 ASSETS / Path(raw_name).with_suffix(".jpg"),
                 ASSETS / "raw" / Path(raw_name).with_suffix(".jpg")]
        raw = next((c for c in cands if c.exists()), cands[0])
        if not raw.exists():
            print(f"  пропуск {raw_name} (нет файла)")
            continue
        img = Image.open(raw)
        cut = cut_white_bg(img)
        cut = trim(cut)
        sprite = fit_canvas(cut, size=args.size)
        dst = ASSETS / out_name
        sprite.save(dst, "PNG", optimize=True)
        # статистика: сколько непрозрачных пикселей
        a = sprite.getchannel("A")
        solid = sum(1 for v in a.getdata() if v > 128)
        print(f"  {raw_name} {img.size} -> {out_name} {sprite.size} непрозрачных {solid/sprite.width/sprite.height*100:.0f}%")
        done += 1
    print(f"готово {done} спрайтов в {ASSETS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
