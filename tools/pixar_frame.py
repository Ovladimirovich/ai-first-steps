#!/usr/bin/env python3
"""
PixarFrame — отрисовка кадра «мультфильм с персонажами» на Pillow.

Собирает кадр 1920x1080 из:
  * пер-сценного фона   assets/pixar/scene_<scene>.jpg  (fallback: общий фон + проекция сцены)
  * спрайтов персонажей assets/pixar/bit*.png / masha*.png (эмоции neutral/surprised/happy)
  * карточки реплики внизу с пословной караоке-подсветкой
  * титула сцены сверху + прогресс-бара внизу

Говорящий — крупнее (scale 1.0), с подсветкой-ореолом и подъёмом; слушающий — 0.9, приглушён.
У Бита покачивание (parallax) сильнее, у обоих «дыхание».

Импортируется в tools/build_ffmpeg_video.py, но можно смотреть и отдельно:
  python tools/pixar_frame.py --scene 1.1 --who b --text "Привет!" --out /tmp/frame.png
"""
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "pixar"

P = {
    "bg": "#FFF6E0",
    "card": "#243A66",
    "card2": "#1B2A4A",
    "teal": "#2EE6D6",
    "yellow": "#FFD23F",
    "coral": "#FF6B6B",
    "cream": "#FFF8E7",
    "text": "#F4F6FA",
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

# эвристика эмоций по тексту реплики (перекрывается assets/pixar/expressions.json)
SURPRISE_WORDS = ("за десять", "вау", "ого", "серьёзно", "не может быть", "как в кино",
                  "то есть я", "прямо сейчас", "?!", "??")
HAPPY_WORDS = ("поехали", "точно", "здорово", "класс", "хочу", "сможешь", "да!", "ага",
               "и ты сможешь", "звучит")


def emotion_for(text, who):
    t = text.lower()
    if any(w in t for w in SURPRISE_WORDS):
        return "surprised"
    if any(w in t for w in HAPPY_WORDS) or t.count("!") >= 2:
        return "happy"
    return "neutral"


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _font(size, bold=False):
    from PIL import ImageFont
    cands = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


class FrameRenderer:
    """Кэширует фоны/спрайты/шрифты/перенос строк и рисует кадры."""

    def __init__(self, W=1920, H=1080, sprites=True, scene_dir=None, fallback_bg=None,
                 show_title=True, show_progress=True, design="movie", camera=True):
        from PIL import Image
        self.W, self.H = W, H
        self.sprites_on = sprites
        self.scene_dir = Path(scene_dir) if scene_dir else ASSETS
        self.design = design
        self.camera = camera
        self.show_title = show_title
        self.show_progress = show_progress
        self._bg_cache = {}
        self._sprite_cache = {}
        self._layout_cache = {}
        self._scrim_cache = {}
        self.fallback_bg = None
        if fallback_bg and Path(fallback_bg).exists():
            self.fallback_bg = Image.open(fallback_bg).convert("RGB")
        # пул базовых фонов для сцен без своего scene_<scene>.jpg
        self.pool = []
        if self.scene_dir.exists():
            for p in sorted(self.scene_dir.glob("bgpool_*.jpg")):
                self.pool.append(p)
        if not self.pool and self.fallback_bg is not None:
            self.pool = [fallback_bg]

        # шрифты под размер кадра
        k = H / 1080.0
        self.f_title = _font(int(46 * k), bold=True)
        self.f_name = _font(int(30 * k), bold=True)
        self.f_body = _font(int(40 * k))
        self.f_small = _font(int(24 * k))
        self.k = k

        # геометрия
        self.card_w = int(1040 * (W / 1920.0))
        self.char_h = int(680 * k)
        self.baseline = H - int(72 * k)

        # спрайты
        self.sprites = {}
        if self.sprites_on:
            for who in ("b", "m"):
                base = "bit" if who == "b" else "masha"
                for emo in ("neutral", "surprised", "happy"):
                    name = f"{base}.png" if emo == "neutral" else f"{base}_{emo}.png"
                    p = self.scene_dir / name
                    if p.exists():
                        self.sprites[(who, emo)] = Image.open(p).convert("RGBA")
                if not any((who, e) in self.sprites for e in ("neutral", "surprised", "happy")):
                    p = self.scene_dir / f"{base}.png"
                    if p.exists():
                        self.sprites[(who, "neutral")] = Image.open(p).convert("RGBA")

    # ---------- ресурсы ----------
    def _sprite(self, who, emo, height, dim=None):
        """Спрайт нужной высоты (+ опционально затемнённый) с кэшем."""
        from PIL import Image, ImageEnhance
        key = (who, emo, height, dim)
        if key in self._sprite_cache:
            return self._sprite_cache[key]
        src = self.sprites.get((who, emo)) or self.sprites.get((who, "neutral"))
        if src is None:
            return None
        w = max(1, int(src.width * height / src.height))
        img = src.resize((w, height), Image.LANCZOS)
        if dim is not None and dim < 1.0:
            img = ImageEnhance.Brightness(img).enhance(dim)
            img = ImageEnhance.Color(img).enhance(0.75)
            a = img.getchannel("A").point(lambda v: int(v * 0.88))
            img.putalpha(a)
        self._sprite_cache[key] = img
        return img

    def _bg(self, scene, idx):
        """Фон сцены: scene_<scene>.jpg, иначе fallback + уникальная обработка под сцену."""
        from PIL import Image, ImageEnhance, ImageDraw, ImageFilter
        if scene in self._bg_cache:
            return self._bg_cache[scene]
        W, H = self.W, self.H
        variant = self._scene_variant(scene, idx)
        p = self.scene_dir / f"scene_{scene}.jpg"
        img = None
        if p.exists():
            try:
                img = Image.open(p).convert("RGB")
            except Exception:
                img = None
        if img is None and self.pool:
            # детерминированный выбор из пула + уникальная проекция сцены
            chosen = self.pool[variant["pool_idx"] % len(self.pool)]
            try:
                img = Image.open(str(chosen)).convert("RGB")
            except Exception:
                img = self.fallback_bg.copy() if self.fallback_bg is not None else None
            if img is not None:
                img = self._reproject(img, variant)
        elif img is None and self.fallback_bg is not None:
            img = self.fallback_bg.copy()
            # уникальная проекция: сдвиг/зум/тонирование, чтобы каждая сцена выглядела своей
            img = self._reproject(img, variant)
        if img is None:
            img = Image.new("RGB", (W, H), hex_to_rgb(P["bg"]))
        # масштаб под кадр с обрезкой по центру
        img = self._cover(img, W, H)
        # лёгкое тонирование сцены
        tint = variant["tint"]
        if tint != (0, 0, 0):
            ov = Image.new("RGB", (W, H), tint)
            img = Image.blend(img, ov, variant["tint_a"])
        # запас под панораму камеры
        if self.camera:
            bw, bh = int(W * 1.06), int(H * 1.06)
            img = self._cover(img, bw, bh)
        # винетка + затемнение под карточку и персонажей
        img = self._scrim(img, variant)
        img = img.convert("RGB")
        self._bg_cache[scene] = img
        return img

    # «лук» блоков сценария: тон + сила + размытие + зум
    BLOCK_LOOK = {
        "0": ("#1A2340", 0.30, 2.4, 1.08),   # ночная спальня / заставка
        "1": ("#3C2A10", 0.20, 1.8, 1.02),   # школа и репетитор, тёплый
        "2": ("#2A1040", 0.26, 2.2, 1.10),   # мастерская идей, фиолет
        "3": ("#0E2A4A", 0.30, 2.6, 1.06),   # чек-вопрос, синий
        "4": ("#0C2E28", 0.26, 2.0, 1.04),   # лаборатория, зелёный
        "5": ("#3A1A22", 0.26, 2.2, 1.12),   # город будущего, закат
        "6": ("#301018", 0.30, 2.6, 1.05),   # осторожно, красный
        "7": ("#161E44", 0.30, 2.8, 1.03),   # чек-вопрос 2
        "8": ("#3A2C0A", 0.22, 1.6, 1.10),   # финал, золото
    }

    def _scene_variant(self, scene, idx):
        """Детерминированная «проекция» сцены, когда нет персонального фона."""
        block = str(scene).split(".")[0]
        t_hex, t_a, blur, zoom = self.BLOCK_LOOK.get(block, ("#1B2A4A", 0.24, 2.0, 1.05))
        # распределяем сцены по пулу так, чтобы соседние брали разные картинки
        pool_idx = int(block) * 2 + (idx % 2) if block.isdigit() else idx
        return {
            "pool_idx": pool_idx,
            "idx": idx,
            "zoom": zoom + 0.02 * (idx % 3),
            "dx": ((idx * 7) % 5 - 2) * 0.05,
            "dy": ((idx * 3) % 5 - 2) * 0.04,
            "flip": False,  # зеркалить нельзя: на фонах бывает текст
            "tint": hex_to_rgb(t_hex),
            "tint_a": t_a,
            "blur": blur,
            "glow": P["teal"] if idx % 2 == 0 else P["coral"],
        }

    def _reproject(self, img, v):
        from PIL import Image, ImageFilter
        W, H = self.W, self.H
        if v["flip"]:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        z = v["zoom"]
        nw, nh = int(W * z), int(H * z)
        img = img.resize((nw, nh), Image.LANCZOS)
        x = int((nw - W) / 2 + v["dx"] * nw)
        y = int((nh - H) / 2 + v["dy"] * nh)
        x = max(0, min(nw - W, x)); y = max(0, min(nh - H, y))
        img = img.crop((x, y, x + W, y + H))
        # размытие сильнее у дальних сцен — «киношная» глубина
        return img.filter(ImageFilter.GaussianBlur(v.get("blur", 1.6)))

    def _cover(self, img, W, H):
        from PIL import Image
        s = max(W / img.width, H / img.height)
        nw, nh = int(img.width * s + 0.5), int(img.height * s + 0.5)
        img = img.resize((nw, nh), Image.LANCZOS)
        x = (nw - W) // 2; y = (nh - H) // 2
        return img.crop((x, y, x + W, y + H))

    def _scrim(self, img, v):
        """Винетка + затемнение снизу под карточку + световое пятно сцены сверху."""
        from PIL import Image, ImageDraw, ImageFilter
        W, H = img.width, img.height
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov, "RGBA")
        # затемнение нижней половины (карточка и персонажи читаются)
        for yy in range(0, H, 4):
            t = yy / H
            a = 0
            if t > 0.40:
                a = int(150 * ((t - 0.40) / 0.60) ** 1.25)
            if t < 0.16:
                a = max(a, int(70 * (1 - t / 0.16)))
            d.rectangle([0, yy, W, yy + 4], fill=(6, 10, 22, a))
        # винетка по краям
        vig = Image.new("L", (W // 4, H // 4), 0)
        vd = ImageDraw.Draw(vig)
        vd.ellipse([-W // 12, -H // 12, W // 4 + W // 12, H // 4 + H // 12], fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(24)).resize((W, H), Image.LANCZOS)
        dark = Image.new("RGBA", (W, H), (4, 8, 18, 120))
        dark.putalpha(Image.eval(vig, lambda x: int((255 - x) * 0.45)))
        ov = Image.alpha_composite(ov, dark)
        return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    # ---------- текст ----------
    def _layout(self, text, progress=0.5):
        """Переносы + позиции слов для караоке. Кэш по тексту."""
        from PIL import Image, ImageDraw
        if text in self._layout_cache:
            return self._layout_cache[text]
        W, H = self.W, self.H
        k = self.k
        card_w = self.card_w
        inner_w = card_w - int(96 * k)
        tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        words = text.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            if tmp.textlength(test, font=self.f_body) <= inner_w or not cur:
                cur.append(w)
            else:
                lines.append(cur)
                cur = [w]
        if cur:
            lines.append(cur)
        line_h = int(56 * k)
        text_h = len(lines) * line_h
        card_h = int(96 * k) + text_h + int(34 * k)
        card_h = max(int(230 * k), min(card_h, int(560 * k)))
        card_x = (W - card_w) // 2
        card_y = self.baseline - card_h - int(20 * k)
        # координаты слов
        placed = []
        ty0 = card_y + int(92 * k)
        for i, line in enumerate(lines):
            x = card_x + int(48 * k)
            y = ty0 + i * line_h
            for w in line:
                wpx = tmp.textlength(w, font=self.f_body)
                spx = tmp.textlength(" ", font=self.f_body)
                placed.append((w, int(x), y, int(wpx)))
                x += wpx + spx
        layout = {"lines": lines, "card": (card_x, card_y, card_w, card_h),
                  "words": placed, "line_h": line_h}
        self._layout_cache[text] = layout
        return layout

    # ---------- кадр ----------
    def render(self, text="", who="b", scene="0.1", s=1.0, karaoke_frac=1.0,
               t=0.0, is_gap=False, progress=None, emotion=None, scene_index=None):
        from PIL import Image, ImageDraw, ImageFilter
        W, H = self.W, self.H
        k = self.k
        if emotion is None and not is_gap and text:
            emotion = emotion_for(text, who)
        idx = scene_index if scene_index is not None else self._scene_idx(scene)
        bg = self._bg(scene, idx)
        if self.camera and bg.width > W:
            # медленный панорамный дрейф + «дыхание» камеры
            span_x = bg.width - W
            span_y = bg.height - H
            ph = idx * 1.31
            ox = int(span_x * (0.5 + 0.5 * math.sin(t / 26.0 + ph)))
            oy = int(span_y * (0.5 + 0.5 * math.sin(t / 19.0 + ph * 1.7)))
            bg = bg.crop((min(span_x, max(0, ox)), min(span_y, max(0, oy)),
                          min(span_x, max(0, ox)) + W, min(span_y, max(0, oy)) + H))
        img = bg.convert("RGBA")

        # персонажи (в паузе — оба спокойно дышат, без подсветки)
        if self.sprites_on and self.sprites:
            img = self._draw_characters(img, who=who, scene_idx=idx, t=t,
                                        active=(None if is_gap else who),
                                        emotion=emotion if not is_gap else None,
                                        fade=min(1.0, s * 1.6 if not is_gap else 1.0))

        draw = ImageDraw.Draw(img, "RGBA")
        # титул сцены сверху в «пилюле»
        if self.show_title:
            title = SCENE_TITLES.get(scene, f"Сцена {scene}")
            tw = draw.textlength(title, font=self.f_title)
            pad = int(30 * k)
            pill = [ (W - tw) / 2 - pad, int(28 * k), (W + tw) / 2 + pad, int(28 * k) + int(76 * k) ]
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer, "RGBA")
            ld.rounded_rectangle(pill, radius=int(38 * k), fill=(10, 16, 32, int(120 * s)))
            ld.rounded_rectangle(pill, radius=int(38 * k), outline=(255, 255, 255, int(26 * s)), width=2)
            img = Image.alpha_composite(img, layer)
            draw = ImageDraw.Draw(img, "RGBA")
            draw.text(((W - tw) / 2, int(40 * k)), title, font=self.f_title, fill=(255, 255, 255, int(240 * s)))
            # счётчик сцены
            cnt = f"{idx + 1}/{len(SCENE_TITLES)}"
            draw.text((int(46 * k), int(50 * k)), cnt, font=self.f_small, fill=(255, 255, 255, int(120 * s)))

        if not is_gap and text and s > 0.001:
            img = self._draw_card(img, text, who, s, karaoke_frac)

        # прогресс-бар по всему ролику
        if self.show_progress and progress is not None:
            bar_y = H - int(10 * k)
            draw.rectangle([0, bar_y, W, H], fill=(255, 255, 255, 26))
            draw.rectangle([0, bar_y, int(W * max(0.0, min(1.0, progress))), H], fill=hex_to_rgb(P["yellow"]) + (235,))
        return img.convert("RGB")

    def _scene_idx(self, scene):
        keys = list(SCENE_TITLES.keys())
        return keys.index(scene) if scene in keys else 0

    def _draw_characters(self, img, who, scene_idx, t, active, emotion, fade=1.0):
        """Персонажи с «дыханием», parallax, ореолом у говорящего и приглушением слушателя."""
        from PIL import Image, ImageDraw, ImageFilter
        W, H = self.W, self.H
        k = self.k
        height = self.char_h
        out = img
        # позиции: Бит слева, Маша справа
        specs = [
            ("b", int(238 * k), 0.0),   # x-центр, фаза
            ("m", W - int(238 * k), 1.7),
        ]
        for side, (cw, cx, phase) in enumerate(specs):
            is_active = (active == cw)
            is_listening = active is not None and not is_active
            emo = "neutral"
            if is_active and emotion:
                emo = emotion
            sprite = self._sprite(cw, emo, height, dim=(1.0 if is_active or active is None else 0.68))
            if sprite is None:
                continue
            # дыхание + parallax (у Бита левитация/покачивание сильнее)
            amp = 9.0 if cw == "b" else 4.0
            bob = math.sin(2 * math.pi * t / (2.6 if cw == "b" else 3.4) + phase) * amp * k
            drift = math.sin(2 * math.pi * t / (7.5 if cw == "b" else 9.5) + phase) * (10 if cw == "b" else 6) * k
            if is_active:
                bob -= 12 * k  # подъём говорящего
                bob += math.sin(2 * math.pi * t * 2.1) * 3 * k  # «жестикуляция»
            scale = 1.0 if is_active else (0.90 if is_listening else 0.95)
            if scale != 1.0:
                sw, sh = int(sprite.width * scale), int(sprite.height * scale)
                spr = sprite.resize((sw, sh), Image.LANCZOS)
            else:
                spr = sprite
            # плавное появление
            alpha = spr.getchannel("A")
            if fade < 1.0:
                spr = spr.copy()
                spr.putalpha(alpha.point(lambda v: int(v * max(0.0, fade))))
            x = int(cx - spr.width / 2 + drift)
            y = int(self.baseline - spr.height + bob)
            # контактная тень на «полу» — привязывает фигуру к сцене
            out = self._ground_shadow(out, cx + drift, y + spr.height, spr.width)
            # ореол у говорящего
            if is_active:
                out = self._glow(out, cw, x + spr.width // 2, y + spr.height // 2, spr.width, spr.height, t)
            out.alpha_composite(spr, (max(0, min(W - spr.width, x)), max(0, min(H - spr.height, y))))
            # тень под ногами
            if not is_active:
                pass
        return out

    def _ground_shadow(self, img, cx, foot_y, spr_w):
        """Мягкая эллиптическая тень под ногами персонажа."""
        from PIL import Image, ImageDraw, ImageFilter
        k = self.k
        W, H = self.W, self.H
        ew = max(20, int(spr_w * 0.78))
        eh = max(8, int(34 * k))
        key = ("ground", ew // 6, eh // 4)
        if key not in self._scrim_cache:
            sw, sh = ew, eh * 3
            g = Image.new("L", (max(2, sw // 2), max(2, sh // 2)), 0)
            gd = ImageDraw.Draw(g)
            gd.ellipse([0, 0, max(1, sw // 2 - 1), max(1, sh // 2 - 1)], fill=255)
            g = g.filter(ImageFilter.GaussianBlur(9)).resize((sw, sh), Image.LANCZOS)
            layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            layer.putalpha(Image.eval(g, lambda v: int(v * 0.55)))
            self._scrim_cache[key] = layer
        lay = self._scrim_cache[key]
        x = int(cx - lay.width / 2)
        y = int(foot_y - lay.height * 0.42)
        x = max(0, min(W - lay.width, x))
        y = max(0, min(H - lay.height, y))
        out = img.copy()
        out.alpha_composite(lay, (x, y))
        return out

    def _glow(self, img, who, cx, cy, w, h, t):
        from PIL import Image, ImageDraw, ImageFilter
        k = self.k
        key = (who, w // 8, h // 8)
        if key not in self._scrim_cache:
            gw, gh = max(2, w + int(150 * k)), max(2, h + int(150 * k))
            g = Image.new("L", (gw // 4, gh // 4), 0)
            gd = ImageDraw.Draw(g)
            gd.ellipse([gw // 8, gh // 8, gw // 4 - gw // 8, gh // 4 - gh // 8], fill=255)
            g = g.filter(ImageFilter.GaussianBlur(18)).resize((gw, gh), Image.LANCZOS)
            col = hex_to_rgb(P["teal"] if who == "b" else P["coral"])
            layer = Image.new("RGBA", (gw, gh), col + (0,))
            layer.putalpha(Image.eval(g, lambda v: int(v * 0.42)))
            self._scrim_cache[key] = layer
        layer = self._scrim_cache[key]
        # пульсация
        pulse = 1.0 + 0.04 * math.sin(2 * math.pi * t * 1.6)
        lw, lh = int(layer.width * pulse), int(layer.height * pulse)
        lay = layer.resize((lw, lh), Image.LANCZOS) if pulse != 1.0 else layer
        out = img.copy()
        out.alpha_composite(lay, (max(0, cx - lw // 2), max(0, cy - lh // 2)))
        return out

    def _draw_card(self, img, text, who, s, karaoke_frac):
        from PIL import Image, ImageDraw, ImageFilter
        W, H = self.W, self.H
        k = self.k
        lay = self._layout(text)
        cx, cy, cw, ch = lay["card"]
        # пружина: подъезд снизу + scale + прозрачность
        scale = 0.94 + 0.06 * min(1.0, s)
        y_off = (1 - min(1.0, s)) * int(70 * k)
        opacity = int(255 * min(1.0, s * 1.15))
        nw, nh = int(cw * scale), int(ch * scale)
        x = int(cx + (cw - nw) / 2)
        y = int(cy + (ch - nh) / 2 + y_off)
        # тень
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle([x + int(14 * k), y + int(20 * k), x + nw + int(14 * k), y + nh + int(20 * k)],
                             radius=int(34 * k), fill=(0, 0, 0, int(110 * s)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(int(18 * k)))
        out = Image.alpha_composite(img, shadow)
        # карточка
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card, "RGBA")
        col = hex_to_rgb(P["teal"]) if who == "b" else hex_to_rgb(P["coral"])
        cd.rounded_rectangle([x, y, x + nw, y + nh], radius=int(34 * k),
                             fill=hex_to_rgb(P["card"]) + (int(opacity * 0.96),),
                             outline=(255, 255, 255, int(30 * s)), width=2)
        # верхняя полоска-акцент цвета спикера
        cd.rounded_rectangle([x, y, x + nw, y + int(8 * k)], radius=int(4 * k), fill=col + (opacity,))
        # блик
        cd.rounded_rectangle([x + int(20 * k), y + int(10 * k), x + nw - int(20 * k), y + int(26 * k)],
                             radius=int(8 * k), fill=(255, 255, 255, int(26 * s)))
        # чип имени
        name = "БИТ" if who == "b" else "МАША"
        nw_px = cd.textlength(name, font=self.f_name)
        chip_w = int(nw_px) + int(58 * k)
        chip = [x + int(40 * k), y + int(30 * k), x + int(40 * k) + chip_w, y + int(30 * k) + int(48 * k)]
        cd.rounded_rectangle(chip, radius=int(24 * k), fill=col + (int(opacity * 0.9),))
        cd.ellipse([chip[0] + int(14 * k), chip[1] + int(14 * k), chip[0] + int(34 * k), chip[1] + int(34 * k)],
                   fill=(255, 255, 255, opacity))
        cd.text((chip[0] + int(44 * k), chip[1] + int(7 * k)), name, font=self.f_name,
                fill=(12, 20, 36, opacity))
        out = Image.alpha_composite(out, card)
        d = ImageDraw.Draw(out, "RGBA")
        # текст с караоке
        words = lay["words"]
        hl = int(len(words) * max(0.0, min(1.0, karaoke_frac)))
        for i, (w, wx, wy, wpx) in enumerate(words):
            lit = i < hl
            # координаты с учётом scale/сдвига
            px = int(x + (wx - cx) * scale)
            py = int(y + (wy - cy) * scale + y_off * 0)
            f = self.f_body
            if lit:
                d.text((px, py), w, font=f, fill=hex_to_rgb(P["yellow"]) + (opacity,))
                d.text((px, py), w, font=f, fill=(255, 220, 120, int(70 * s)))
            else:
                d.text((px, py), w, font=f, fill=hex_to_rgb(P["text"]) + (int(opacity * 0.94),))
        # пословный «маркер» на текущем слове — мягкое подчёркивание
        if 0 < hl <= len(words):
            w, wx, wy, wpx = words[hl - 1]
            ux = int(x + (wx - cx) * scale)
            uy = int(y + (wy - cy) * scale) + int(46 * k)
            d.rounded_rectangle([ux, uy, ux + int(wpx * scale), uy + int(5 * k)], radius=3,
                                fill=hex_to_rgb(P["yellow"]) + (int(140 * s),))
        return out


def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="1.1")
    ap.add_argument("--who", default="b")
    ap.add_argument("--text", default="На уроке не понял фотосинтез? Учитель объяснил быстро, спросить стесняешься?")
    ap.add_argument("--out", default="/tmp/frame.png")
    ap.add_argument("--time", type=float, default=0.0)
    ap.add_argument("--karaoke", type=float, default=0.55)
    ap.add_argument("--sprites", action="store_true", default=True)
    ap.add_argument("--no-sprites", dest="sprites", action="store_false")
    ap.add_argument("--bg", default=str(ROOT / "pixar-style-preview.jpg"))
    args = ap.parse_args()
    r = FrameRenderer(sprites=args.sprites, fallback_bg=args.bg)
    img = r.render(args.text, args.who, args.scene, s=1.0, karaoke_frac=args.karaoke,
                   t=args.time, progress=0.3)
    img.save(args.out)
    print(f"ok {args.out} {img.size}")


if __name__ == "__main__":
    _cli()
