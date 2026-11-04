#!/usr/bin/env python3
"""
Собирает 25 пер-сценных фонов assets/pixar/scene_<scene>.jpg из базовых картинок.

Зачем: у каждой сцены должен быть свой фон, но генерить 25 картинок дорого/долго.
Скрипт берёт базовые изображения (bgpool_*.jpg — сгенерированные Pixar-планы) и делает
для каждой сцены СВОЙ кадр: свой кроп (зум/смещение), своя цветокоррекция (тон, яркость,
контраст, насыщенность), мягкая виньетка и подсветка под настроение блока сценария.

Если положить свой файл scene_<scene>.jpg ДО запуска — он не тронется (--force чтобы перезаписать).

usage:
  python tools/make_scene_backgrounds.py            # сгенерировать недостающие
  python tools/make_scene_backgrounds.py --force    # перезаписать все
  python tools/make_scene_backgrounds.py --list     # что будет использовано
"""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "pixar"

# настроение блоков: (тон, сила тона, яркость, контраст, насыщенность, зум)
BLOCKS = {
    "0": ("#1B2A52", 0.34, 0.92, 1.06, 1.05, 1.30),   # ночь, спальня/заставка
    "1": ("#4A3210", 0.20, 1.04, 1.04, 1.06, 1.24),   # школа, тёплый день
    "2": ("#3A1352", 0.30, 1.00, 1.08, 1.10, 1.34),   # мастерская, фиолет/неон
    "3": ("#0E2E56", 0.34, 0.98, 1.08, 1.04, 1.26),   # викторина, синий
    "4": ("#0E3A32", 0.28, 1.02, 1.06, 1.08, 1.30),   # лаборатория, зелёный
    "5": ("#4A1E16", 0.26, 1.02, 1.06, 1.10, 1.36),   # город будущего, закат
    "6": ("#3C0E16", 0.32, 0.90, 1.10, 0.95, 1.28),   # осторожно, тревожный
    "7": ("#141C4C", 0.34, 0.98, 1.06, 1.02, 1.24),   # викторина 2
    "8": ("#4A3608", 0.22, 1.06, 1.04, 1.12, 1.32),   # финал, золото
}

# какая база под какой блок (индексы в пуле)
BLOCK_POOL = {
    "0": [0, 1],      # спальня, звёздная сцена
    "1": [2, 4],      # класс, мастерская
    "2": [1, 3],      # звёздная сцена, пиццерия (тёплые полки)
    "3": [1, 0],      # сцена, спальня
    "4": [4, 2],      # мастерская, класс
    "5": [0, 3],      # спальня (городские огни), пиццерия
    "6": [2, 1],      # класс, сцена
    "7": [1, 4],      # сцена, мастерская
    "8": [3, 0],      # пиццерия (тёплые полки), спальня
}

SCENES = ["0.1", "0.2", "1.1", "1.2", "1.3", "1.4", "2.1", "2.2", "2.3", "2.4",
          "3.1", "4.1", "4.2", "4.3", "4.4", "5.1", "5.2", "5.3", "5.4",
          "6.1", "6.2", "6.3", "7.1", "8.1", "8.2"]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def seed_of(scene):
    return int(hashlib.md5(scene.encode()).hexdigest()[:8], 16)


def pick_pool(scene, idx):
    block = scene.split(".")[0]
    options = BLOCK_POOL.get(block, [0])
    return options[idx % len(options)]


def make_one(base_paths, scene, idx, size=(1920, 1080)):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    W, H = size
    block = scene.split(".")[0]
    tint, tint_a, bright, contrast, sat, zoom = BLOCKS.get(block, ("#1B2A4A", 0.25, 1.0, 1.04, 1.05, 1.25))
    rnd = seed_of(scene)

    base = base_paths[pick_pool(scene, idx) % len(base_paths)]
    img = Image.open(str(base)).convert("RGB")

    # 1) свой кроп: зум + смещение, детерминированно от сцены
    z = zoom + ((rnd % 100) / 100.0) * 0.22
    nw, nh = int(W * z), int(H * z)
    # кроп из базы 16:9-ish: масштабируем базу до nw x auto
    s = max(nw / img.width, nh / img.height)
    big = img.resize((max(1, int(img.width * s + 0.5)), max(1, int(img.height * s + 0.5))), Image.LANCZOS)
    max_x, max_y = max(0, big.width - nw), max(0, big.height - nh)
    ox = int(max_x * (((rnd >> 3) % 100) / 100.0))
    oy = int(max_y * (((rnd >> 7) % 100) / 100.0))
    img = big.crop((ox, oy, ox + nw, oy + nh)).resize((W, H), Image.LANCZOS)

    # 2) цветокоррекция сцены
    img = Image.blend(img, Image.new("RGB", (W, H), hex_to_rgb(tint)), tint_a)
    img = ImageEnhance.Brightness(img).enhance(bright)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(sat)

    # 3) «свой характер»: у чётных сцен — тёплый световой блик, у нечётных — холодная дымка
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    if idx % 2 == 0:
        cx = int(W * (0.15 + ((rnd >> 11) % 60) / 100.0))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([cx - 520, -380, cx + 520, 420], fill=(255, 214, 150, 62))
        glow = glow.filter(ImageFilter.GaussianBlur(150))
        ov = Image.alpha_composite(ov, glow)
    else:
        haze = Image.new("RGBA", (W, H), (120, 190, 255, 26))
        haze = haze.filter(ImageFilter.GaussianBlur(2))
        ov = Image.alpha_composite(ov, haze)

    # 4) винетка и затемнение низа/верха под карточку и титул
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dark)
    for y in range(0, H, 6):
        t = y / H
        a = 0
        if t > 0.55:
            a = int(120 * ((t - 0.55) / 0.45) ** 1.3)
        if t < 0.18:
            a = max(a, int(60 * (1 - t / 0.18)))
        dd.rectangle([0, y, W, y + 6], fill=(4, 8, 18, a))
    vig = Image.new("L", (W // 4, H // 4), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-W // 14, -H // 14, W // 4 + W // 14, H // 4 + H // 14], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(26)).resize((W, H), Image.LANCZOS)
    edge = Image.new("RGBA", (W, H), (2, 6, 14, 150))
    edge.putalpha(Image.eval(vig, lambda v: int((255 - v) * 0.5)))
    ov = Image.alpha_composite(ov, dark)
    ov = Image.alpha_composite(ov, edge)

    out = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    # 5) лёгкая киношная мягкость + микрозерно, чтобы апскейл не выглядел цифровым
    out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=55, threshold=3))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="перезаписать существующие scene_*.jpg")
    ap.add_argument("--list", action="store_true", help="только показать план")
    args = ap.parse_args()

    pool = sorted(ASSETS.glob("bgpool_*.jpg"))
    if not pool:
        # базы могут лежать в raw/ как исходные генерации
        pool = sorted(list((ASSETS / "raw").glob("_bg_*.jpg")) + list((ASSETS / "raw").glob("_bg_*.png")))
    if not pool:
        print(f"нет базовых фонов bgpool_*.jpg в {ASSETS}")
        return 1
    print(f"базовых фонов: {len(pool)} -> {[p.name for p in pool]}")
    made = skipped = 0
    for idx, scene in enumerate(SCENES):
        dst = ASSETS / f"scene_{scene}.jpg"
        base = pool[pick_pool(scene, idx) % len(pool)]
        if args.list:
            print(f"  {scene:>4} <- {base.name} (кроп+грейд блока {scene.split('.')[0]})")
            continue
        if dst.exists() and not args.force:
            skipped += 1
            continue
        img = make_one(pool, scene, idx)
        img.save(dst, "JPEG", quality=93, optimize=True)
        made += 1
        print(f"  {scene:>4} <- {base.name} -> {dst.name} {dst.stat().st_size // 1024}КБ")
    if not args.list:
        print(f"готово: сделано {made}, пропущено {skipped} (были на месте)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
