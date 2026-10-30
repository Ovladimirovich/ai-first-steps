#!/usr/bin/env python3
"""
FFmpeg / MoviePy быстрый рендер Pixar WHY AI — 2-4 мин вместо 50 мин Remotion.
Берёт те же timing-pixar.json + voice_track-pixar.mp3 + Pillow-отрисовку карточек.
Работает на Windows 10 / Ubuntu / GitHub Actions, без Chrome.

usage:
  python tools/build_ffmpeg_video.py                          # -> ../release/pixar-why-ai-ffmpeg.mp4
  python tools/build_ffmpeg_video.py --preview                # 720p + crf 23 + ultrafast (1 мин)
  python tools/build_ffmpeg_video.py --output preview/test.mp4 --no-audio
  python tools/build_ffmpeg_video.py --only 5                 # первые 5 реплик для теста 20 сек
"""
import argparse, json, os, sys, textwrap, math
from pathlib import Path

# --- пути ---
ROOT = Path(__file__).resolve().parent.parent
TIMING = ROOT / "remotion" / "public" / "timing-pixar.json"
VOICE = ROOT / "remotion" / "public" / "audio" / "voice_track-pixar.mp3"
VOICE_PREVIEW = ROOT / "preview" / "voice_track-pixar.mp3"
ASSETS = ROOT / "assets" / "pixar"
OUT_DEFAULT = ROOT / "release" / "pixar-why-ai-ffmpeg.mp4"

# --- тема как в pixarTheme.ts ---
P = {
    "bg": "#FFF6E0",
    "bg2": "#1B2A4A",
    "teal": "#2EE6D6",
    "yellow": "#FFD23F",
    "coral": "#FF6B6B",
    "cream": "#FFF8E7",
    "wood": "#D9B56A",
}
SCENE_TITLES = {
    "0.1": "Гора домашки",
    "0.2": "4 суперсилы",
    "1.1": "Не понял на уроке?",
    "1.2": "Объясни как для друга",
    "1.3": "Тренер, а не костыль",
    "1.4": "Суперсила 1: Репетитор 24/7",
    "2.1": "Хочу, но не умею рисовать",
    "2.2": "Из шума — в картину",
    "2.3": "Твоя обложка, твой трек",
    "2.4": "Суперсила 2: Творец",
    "3.1": "Чек-вопрос",
    "4.1": "Генератор идей",
    "4.2": "Менеджер проекта",
    "4.3": "Будь детективом",
    "4.4": "Суперсила 3: Исследователь",
    "5.1": "Кем буду работать?",
    "5.2": "Архитектор миров",
    "5.3": "Портфолио сейчас",
    "5.4": "Суперсила 4: Будущее",
    "6.1": "Подвох: галлюцинации",
    "6.2": "3 правила",
    "6.3": "Как работает ИИ",
    "7.1": "ИИ сделает умнее?",
    "8.1": "4 причины дружить",
    "8.2": "Челлендж на неделю",
}

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0,2,4))

def get_font(size, bold=False):
    """Ищет кириллический шрифт на Win/Linux, fallback -> DejaVu -> default"""
    candidates = [
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        # Linux GitHub Actions
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    from PIL import ImageFont
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except: pass
    # last resort
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except:
        return ImageFont.load_default()

def wrap_text(text, font, max_width, draw):
    """Разбивает русский текст по ширине, возвращает список строк"""
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = cur + " " + w if cur else w
        bbox = draw.textbbox((0,0), test, font=font)
        w_px = bbox[2]-bbox[0]
        if w_px <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            # если одно слово длиннее max_width — режем
            bbox_w = draw.textbbox((0,0), w, font=font)[2]
            if bbox_w > max_width:
                # грубый перенос по символам
                chunk = ""
                for ch in w:
                    test2 = chunk + ch
                    if draw.textbbox((0,0), test2, font=font)[2] <= max_width:
                        chunk = test2
                    else:
                        lines.append(chunk)
                        chunk = ch
                cur = chunk
            else:
                cur = w
    if cur:
        lines.append(cur)
    return lines

def draw_pixar_image(text, who, scene, W=1920, H=1080, bg_path=None, is_gap=False):
    """
    Рисует 1920x1080 кадр в стиле PixarCard через Pillow:
    - тёплый фон #FFF6E0 + лёгкий градиент/картинка облаков
    - заголовок сверху
    - объёмная карточка #243A66 с пружинкой-эффектом (статично для ffmpeg)
    - аватар Бита/Маши + текст с переносом
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import random

    # фон
    bg_rgb = hex_to_rgb(P["bg"])
    img = Image.new("RGB", (W, H), bg_rgb)
    draw = ImageDraw.Draw(img, "RGBA")

    # если есть картинка облаков — подмешиваем полупрозрачно
    if bg_path and bg_path.exists():
        try:
            bg = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
            # осветляем и смешиваем
            bg = Image.blend(img, bg, 0.18)
            img = bg
            draw = ImageDraw.Draw(img, "RGBA")
        except: pass
    else:
        # лёгкий градиент: сверху чуть светлее, снизу чуть темнее
        for y in range(H):
            t = y / H
            r = int(bg_rgb[0] * (1 - t*0.04))
            g = int(bg_rgb[1] * (1 - t*0.04))
            b = int(bg_rgb[2] * (1 - t*0.02))
            draw.line([(0, y), (W, y)], fill=(r,g,b))

        # декоративные кружки как в PS сценах
        for _ in range(6):
            x = random.randint(-100, W-100)
            y = random.randint(-100, H-100)
            rr = random.randint(80, 200)
            col = random.choice([P["teal"], P["yellow"], P["coral"]])
            rgb = hex_to_rgb(col)
            draw.ellipse([x, y, x+rr, y+rr], fill=rgb+(18,))

    # заголовок сверху
    title = SCENE_TITLES.get(scene, f"Сцена {scene}")
    font_title = get_font(58, bold=True)
    # тень заголовка
    bbox = draw.textbbox((0,0), title, font=font_title)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    tx = (W - tw)//2
    ty = 44
    # тень
    draw.text((tx+2, ty+3), title, font=font_title, fill=(0,0,0,70))
    draw.text((tx, ty), title, font=font_title, fill=(27,42,74) if not is_gap else (27,42,74))

    if is_gap:
        # для пауз — только заголовок + декоративная подпись "слушаем..."
        font_hint = get_font(28)
        hint = "— пауза —"
        bbox2 = draw.textbbox((0,0), hint, font=font_hint)
        draw.text(((W-bbox2[2])//2, H//2), hint, font=font_hint, fill=(27,42,74,120))
        return img

    # карточка
    card_w = 1400
    # измерим текст чтобы карточка росла
    font_body = get_font(40)
    font_who = get_font(32, bold=True)
    max_text_w = card_w - 76  # padding 38*2
    # временный draw для замера
    tmp = Image.new("RGB", (W,H))
    tmp_draw = ImageDraw.Draw(tmp)
    who_label = "БИТ" if who == "b" else "МАША"
    lines = wrap_text(text, font_body, max_text_w, tmp_draw)
    # считаем высоту
    line_h = 52
    text_h = len(lines) * line_h
    card_h = 100 + text_h + 30  # верх под аватар + текст + низ
    card_h = max(180, min(card_h, 560))
    card_x = (W - card_w)//2
    card_y = (H - card_h)//2 + 30  # чуть ниже центра

    # тень карточки (размытая)
    shadow_offset = 18
    shadow = Image.new("RGBA", (W, H), (0,0,0,0))
    sdraw = ImageDraw.Draw(shadow)
    # большая тень
    sdraw.rounded_rectangle([card_x+shadow_offset, card_y+shadow_offset, card_x+card_w+shadow_offset, card_y+card_h+shadow_offset], radius=28, fill=(0,0,0,58))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # сама карточка #243A66
    card_rgb = hex_to_rgb("#243A66")
    draw.rounded_rectangle([card_x, card_y, card_x+card_w, card_y+card_h], radius=28, fill=card_rgb, outline=(255,255,255,22), width=1)
    # блик сверху
    draw.rounded_rectangle([card_x+18, card_y, card_x+card_w-18, card_y+18], radius=8, fill=(255,255,255,36))
    # внутренний нижний градиент
    draw.rounded_rectangle([card_x, card_y+card_h-14, card_x+card_w, card_y+card_h], radius=28, fill=(0,0,0,38))

    # аватар кружок слева вверху карточки
    avatar_r = 36
    ax = card_x + 30
    ay = card_y + 28
    who_col = P["teal"] if who == "b" else P["coral"]
    who_rgb = hex_to_rgb(who_col)
    draw.ellipse([ax, ay, ax+avatar_r*2, ay+avatar_r*2], fill=who_rgb, outline=(255,255,255,40), width=2)
    # буква в аватаре
    letter = "B" if who == "b" else "M"
    font_letter = get_font(36, bold=True)
    bbox_l = draw.textbbox((0,0), letter, font=font_letter)
    lx = ax + avatar_r - (bbox_l[2]-bbox_l[0])//2
    ly = ay + avatar_r - (bbox_l[3]-bbox_l[1])//2 -2
    draw.text((lx, ly), letter, font=font_letter, fill=(255,255,255))

    # имя рядом
    draw.text((ax+avatar_r*2+16, ay+18), who_label, font=font_who, fill=(255,255,255,230))

    # текст внутри
    tx0 = card_x + 38
    ty0 = card_y + 88
    for i, line in enumerate(lines):
        y = ty0 + i*line_h
        # лёгкая тень текста
        draw.text((tx0+1, y+1), line, font=font_body, fill=(0,0,0,40))
        draw.text((tx0, y), line, font=font_body, fill=(244,246,250))

    # прогресс-точка внизу карточки
    # маленькая полоска
    pw = int(card_w * 0.72)
    px = card_x + (card_w - pw)//2
    py = card_y + card_h - 18
    draw.rounded_rectangle([px, py, px+pw, py+6], radius=3, fill=(255,255,255,28))
    # заполнение по сцене (декоративно)
    # найдём номер сцены для прогресса
    try:
        scene_idx = list(SCENE_TITLES.keys()).index(scene)
        prog = (scene_idx+1)/len(SCENE_TITLES)
    except: prog = 0.5
    draw.rounded_rectangle([px, py, px+int(pw*prog), py+6], radius=3, fill=hex_to_rgb(P["yellow"]))

    return img

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", "-o", default=str(OUT_DEFAULT), help="выходной mp4")
    ap.add_argument("--crf", type=int, default=18, help="качество 18=высокое 23=меньше файл")
    ap.add_argument("--preset", default="medium", help="ffmpeg preset ultrafast/medium/slow")
    ap.add_argument("--concurrency", type=int, default=4, help="потоки ffmpeg threads")
    ap.add_argument("--preview", action="store_true", help="быстрый превью 720p crf23 ultrafast")
    ap.add_argument("--no-audio", action="store_true", help="без озвучки (для теста)")
    ap.add_argument("--only", type=int, default=0, help="только первые N реплик (для теста)")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    if args.preview:
        args.width = 1280
        args.height = 720
        args.crf = 23
        args.preset = "ultrafast"
        if args.output == str(OUT_DEFAULT):
            args.output = str(ROOT / "preview" / "pixar-why-ai-ffmpeg-preview.mp4")

    W, H = args.width, args.height
    print(f"FFmpeg PIXAR — {W}x{H} crf{args.crf} {args.preset} threads{args.concurrency}")

    # загрузка тайминга
    if not TIMING.exists():
        print(f"не найден {TIMING}", file=sys.stderr); sys.exit(1)
    data = json.loads(TIMING.read_text(encoding="utf-8"))
    lines = data["lines"]
    total = float(data["total"])
    fps = int(data.get("fps", 30))
    if args.only:
        lines = lines[:args.only]
        total = lines[-1]["end"] + 0.5 if lines else total
        print(f"TEST only {args.only} lines -> total {total:.1f}s")

    # аудио
    voice = VOICE if VOICE.exists() else VOICE_PREVIEW
    if not voice.exists():
        print(f"нет аудио {VOICE}", file=sys.stderr)
        args.no_audio = True

    # фон картинка если есть
    bg_path = None
    for p in [ASSETS / "classroom_pixar.jpg", ASSETS / "clouds_pixar_bg.jpg", ROOT/"remotion/public/pixar/clouds_pixar_bg.jpg"]:
        if p.exists():
            bg_path = p; break

    # готовим сегменты: реплика + пауза
    segments = []  # list of (type, text, who, scene, dur)
    for i, ln in enumerate(lines):
        segments.append(("line", ln["text"], ln["who"], ln["scene"], float(ln["dur"])))
        if i+1 < len(lines):
            gap = float(lines[i+1]["start"]) - float(ln["end"])
            if gap > 0.05:
                # пауза — показываем фон сцены без карточки
                segments.append(("gap", "", "b", ln["scene"], gap))
    # хвост до total
    if lines:
        tail = total - float(lines[-1]["end"])
        if tail > 0.05:
            segments.append(("gap", "", "b", lines[-1]["scene"], tail))
    # голова до первой реплики если start >0
    if lines and float(lines[0]["start"]) > 0.05:
        head = float(lines[0]["start"])
        segments.insert(0, ("gap", "", "b", lines[0]["scene"], head))

    print(f"сегментов: {len(segments)} (реплик {len(lines)} + паузы {len(segments)-len(lines)}) суммарно {sum(s[4] for s in segments):.1f}s / {total:.1f}s")

    # проверяем зависимости
    try:
        from PIL import Image
    except ImportError:
        print("ставлю Pillow..."); os.system(f"{sys.executable} -m pip install -q Pillow")
        from PIL import Image
    try:
        import moviepy.editor as mpe
        from moviepy.video.io.ffmpeg_tools import ffmpeg_escape_filename
        HAS_MOVIEPY = True
    except ImportError:
        print("ставлю moviepy..."); os.system(f"{sys.executable} -m pip install -q moviepy")
        import moviepy.editor as mpe
        HAS_MOVIEPY = True

    import tempfile, numpy as np
    tmpdir = Path(tempfile.mkdtemp(prefix="pixar_ffmpeg_"))
    print(f"tmp {tmpdir} — рендерю {len(segments)} картинок...")

    clips = []
    # кэш картинок чтобы не перегенерировать одинаковые gap одной сцены
    cache = {}
    for idx, (typ, text, who, scene, dur) in enumerate(segments):
        # ключ кэша
        key = (typ, who, scene, text[:80]) if typ=="line" else (typ, scene)
        if key in cache:
            img_path = cache[key]
        else:
            is_gap = typ=="gap"
            img = draw_pixar_image(text, who, scene, W=W, H=H, bg_path=bg_path, is_gap=is_gap)
            img_path = tmpdir / f"seg_{idx:03d}_{typ}_{scene.replace('.','_')}.png"
            img.save(img_path, "PNG", compress_level=1)
            cache[key] = img_path
            if idx % 10 == 0:
                print(f"  {idx+1}/{len(segments)} {typ} {scene} {dur:.2f}s -> {img_path.name}")

        # ImageClip из файла (ленивая загрузка, экономит RAM)
        clip = mpe.ImageClip(str(img_path), duration=dur)
        clips.append(clip)

    print(f"склейка {len(clips)} клипов...")
    final = mpe.concatenate_videoclips(clips, method="compose")
    # режем/тянем до total точно (из-за округлений)
    if abs(final.duration - total) > 0.1:
        print(f"подгоняю длительность {final.duration:.2f}s -> {total:.2f}s")
        final = final.subclip(0, total)

    if not args.no_audio and voice.exists():
        print(f"аудио {voice} ({voice.stat().st_size/1024/1024:.1f}МБ)")
        audio = mpe.AudioFileClip(str(voice))
        # подгоняем аудио под видео (обрезаем/петля не нужна, у нас total совпадает)
        if audio.duration < final.duration:
            print(f"аудио короче {audio.duration:.1f}s < {final.duration:.1f}s — добавлю тишину")
            # дополняем тишиной — просто растягиваем видео под аудио? делаем наоборот — режем видео
            final = final.subclip(0, audio.duration)
        else:
            audio = audio.subclip(0, final.duration)
        final = final.set_audio(audio)
        final = final.set_duration(audio.duration)
    else:
        print("без аудио")

    # вывод
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"пишу {out} fps={fps} preset={args.preset} crf={args.crf} threads={args.concurrency}...")
    # moviepy сам найдёт ffmpeg (imageio-ffmpeg)
    # threads — для libx264
    final.write_videofile(
        str(out),
        fps=fps,
        codec="libx264",
        audio_codec="aac" if not args.no_audio else None,
        preset=args.preset,
        threads=args.concurrency,
        ffmpeg_params=["-crf", str(args.crf), "-pix_fmt", "yuv420p"],
        logger="bar",
        # для Windows пути с пробелами
        temp_audiofile=str(tmpdir / "tmp_aud.m4a"),
        remove_temp=True,
    )
    print(f"ГОТОВО {out} {out.stat().st_size/1024/1024:.1f}МБ")
    # чистим
    # import shutil; shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"tmp остаётся {tmpdir} для отладки — можно удалить")

if __name__ == "__main__":
    main()
