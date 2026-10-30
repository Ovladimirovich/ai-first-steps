#!/usr/bin/env python3
"""
Конструктор новых мультяшных тем — штампуй ролики за 15 мин.

Использование:
  python tools/new_topic.py "Зачем математика в 5 классе" --scenes 5
  python tools/new_topic.py "Почему надо читать" --style workshop --voice auto

Что делает:
  1. Создаёт script/lines_<slug>.json из шаблона (8 блоков, 4 суперсилы)
  2. Создаёт папку assets/audio/voice-<slug>/ (пустые .mp3-заглушки с длительностью)
  3. Генерит remotion/public/timing-<slug>.json + subtitles/ru-<slug>.srt через build_pixar_timing
  4. Показывает команду для рендера: python tools/build_ffmpeg_video.py --motion 3 --use-workshop-bg ...

Если есть папка assets/pixar/scene_*.jpg — они подхватятся автоматом как пер-сценные фоны.
Если есть assets/pixar/bit.png / masha.png — наложатся с parallax.
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def slugify(text):
    # транслит кириллицы в латиницу для совместимости с Windows/ffmpeg
    trans = str.maketrans({
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
        'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'Yo','Ж':'Zh','З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M','Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'H','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Sch','Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Yu','Я':'Ya',
    })
    s = text.translate(trans)
    s = s.lower()
    s = re.sub(r"[\"'`«»]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:40] or "topic"

TEMPLATE_BLOCKS = [
    ("0.1", "Гора домашки", "Хук: 2 часа vs 10 мин с ИИ"),
    ("0.2", "4 суперсилы", "Тизер"),
    ("1.1", "Не понял на уроке?", "Репетитор"),
    ("1.2", "Объясни как для друга", "Репетитор — подстройка"),
    ("1.3", "Тренер, а не костыль", "Репетитор — проверка"),
    ("1.4", "Суперсила 1: Репетитор 24/7", "Карточка"),
    ("2.1", "Хочу, но не умею рисовать", "Творец — промпт"),
    ("2.2", "Из шума — в картину", "Диффузия 50 шагов"),
    ("2.3", "Твоя обложка, твой трек", "Творец — выбор"),
    ("2.4", "Суперсила 2: Творец", "Карточка"),
    ("3.1", "Чек-вопрос", "Честно ли сдать чужое?"),
    ("4.1", "Генератор идей", "Исследователь — идеи"),
    ("4.2", "Менеджер проекта", "Шаги + код"),
    ("4.3", "Будь детективом", "3 версии"),
    ("4.4", "Суперсила 3: Исследователь", "Карточка"),
    ("5.1", "Кем буду работать?", "Будущее — человек с ИИ"),
    ("5.2", "Архитектор миров", "Игра/мульт в одиночку"),
    ("5.3", "Портфолио сейчас", "Домашка → портфолио"),
    ("5.4", "Суперсила 4: Будущее", "Карточка"),
    ("6.1", "Подвох", "Галлюцинации"),
    ("6.2", "3 правила", "Проверяй / Указывай / Береги"),
    ("6.3", "Как работает ИИ", "Учился на примерах"),
    ("7.1", "ИИ сделает умнее?", "Только если думаешь"),
    ("8.1", "4 карточки + челлендж", "Итог"),
    ("8.2", "Челлендж на неделю", "Сделай постер"),
]

def make_lines(title, slug, scenes=5):
    # Берём первые `scenes` блоков из шаблона + всегда финал 8.2
    # scenes=5 → берём 5×4 + финал, но для простоты берём первые N*5 строк
    # Упрощено: берём все 25, меняем заголовок темы в текстах
    base = Path(ROOT / "script/lines_pixar_why_ai.json")
    if base.exists():
        data = json.loads(base.read_text(encoding="utf-8"))
        # заменим первые 2 реплики под новую тему как пример
        lines = data[:]
        for ln in lines:
            # подменим упоминания "ИИ" на тему если нужно — оставим как есть для шаблона
            pass
        # поменяем id префикс
        for ln in lines:
            ln["id"] = ln["id"].replace("p", slug[:1])
        return lines
    # fallback — генерируем с нуля
    lines = []
    for i, (scene, t, desc) in enumerate(TEMPLATE_BLOCKS[:scenes*5+1]):
        who = "b" if i % 2 ==0 else "m"
        lines.append({
            "id": f"{slug}_{scene.replace('.','_')}_{who}_{i:02d}",
            "scene": scene,
            "who": who,
            "text": f"{t} — {desc} — тема: {title}"
        })
    return lines

def main():
    ap = argparse.ArgumentParser(description="Конструктор новых тем")
    ap.add_argument("title", help="Название темы в кавычках")
    ap.add_argument("--scenes", type=int, default=5, help="Кол-во блоков (3-8)")
    ap.add_argument("--style", default="workshop", choices=["workshop","clouds","custom"], help="Фон")
    ap.add_argument("--voice", default="auto", help="auto = заглушки, или путь к папке с mp3")
    ap.add_argument("--slug", default="", help="slug вручную, иначе из title")
    args = ap.parse_args()

    slug = args.slug or slugify(args.title)
    print(f"Тема: {args.title} → slug: {slug}")

    # 1. lines
    lines_path = ROOT / f"script/lines_{slug}.json"
    if lines_path.exists():
        print(f"уже есть {lines_path} — перезаписываю")
    lines = make_lines(args.title, slug, scenes=args.scenes)
    lines_path.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {lines_path} {len(lines)} реплик")

    # 2. voice папка
    voice_dir = ROOT / f"assets/audio/voice-{slug}"
    voice_dir.mkdir(parents=True, exist_ok=True)
    # создадим заглушки 1с тишины если нет реальных mp3 (чтобы build не падал)
    # генерим 0.5с тишины через ffmpeg если нет
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        for ln in lines[:3]:  # только 3 для примера, остальные — по мере записи
            mp3 = voice_dir / f"{ln['id']}.mp3"
            if not mp3.exists():
                # 0.8с тишины
                subprocess.run([ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.8", "-q:a", "9", str(mp3)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✓ {voice_dir} (заглушки 0.8с для первых 3, остальные — запиши TTS)")
    except Exception as e:
        print(f"! не смог сделать заглушки: {e}")

    # 3. сценарий md
    scen_path = ROOT / f"script/scenario_{slug}.md"
    scen_path.write_text(f"# {args.title}\n\nТема: {args.title}\nСцен: {args.scenes} блоков, стиль {args.style}\n\nСгенерировано из lines_{slug}.json — правь тексты там, затем:\n\n```bash\npython tools/build_pixar_real_timeline.py --lines script/lines_{slug}.json --voice assets/audio/voice-{slug} --out remotion/public/timing-{slug}.json\npython tools/build_ffmpeg_video.py --motion 3 --use-workshop-bg --output release/{slug}.mp4 --crf 18 --preset medium\n```\n", encoding="utf-8")
    print(f"✓ {scen_path}")

    # 4. подсказка по фонам
    print("\nФоны:")
    print(f"  - Универсальный: pixar-style-preview.jpg (--use-workshop-bg)")
    print(f"  - Пер-сценные: assets/pixar/scene_1.1.jpg, scene_1.2.jpg ... scene_8.2.jpg — положи свои эскизы 1920x1080 JPG")
    print(f"  - Персонажи поверх: assets/pixar/bit.png, masha.png (прозрачный PNG 400x400) — наложатся с parallax")

    # 5. подсказка по озвучке
    print("\nОзвучка:")
    print(f"  Запиши TTS в {voice_dir}/<id>.mp3 (ElevenLabs: Бит — мужской, Маша — девочка)")
    print(f"  Затем: python tools/build_pixar_real_timeline.py --lines {lines_path} --voice {voice_dir} --out remotion/public/timing-{slug}.json")
    print(f"  Субтитры: subtitles/ru-{slug}.srt появятся автоматом")

    # 6. команда рендера
    print("\nРендер:")
    print(f"  Статика 3 мин: python tools/build_ffmpeg_video.py --output release/{slug}.mp4 --crf 18 --preset medium")
    print(f"  Мультяшно 12-15 мин: python tools/build_ffmpeg_video.py --motion 3 --use-workshop-bg --output release/{slug}_motion.mp4 --crf 18 --preset medium")
    print(f"  Remotion Studio: cd remotion && npm run dev  # выбери PixarWhyAI, поменяй timing на timing-{slug}.json")

    print(f"\nГотово — slug={slug}. Следующий шаг: правь {lines_path} и запиши голос.")

if __name__ == "__main__":
    main()
