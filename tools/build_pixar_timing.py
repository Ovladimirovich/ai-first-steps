"""Генерирует timing-pixar.json из lines_pixar_why_ai.json без реальных mp3 — по длине текста (~14.5 симв/сек, как TTS)."""
import json, re, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = json.load(open(f"{R}/script/lines_pixar_why_ai.json", encoding="utf-8"))

# оценка длительности: TTS ~ 135 слов/мин, ~5.5 симв/слово => ~12-15 симв/сек. Берем 14.5, минимум 1.1с
def est_dur(txt):
    c = len(txt)
    # растягиваем до ~11 мин: TTS для детей чуть медленнее + Pixar-паузы
    return max(1.45, c / 14.5 * 2.05)

t = 0.0
prev_scene = None
out = []
for l in lines:
    if prev_scene and l["scene"] != prev_scene:
        t += 1.1  # пауза между сценами чуть меньше чем в оригинале для бодрости
    if l["text"].startswith("Миллиарды") or l["text"].startswith("Проверка!"):
        t += 0.6
    d = est_dur(l["text"])
    # викторины — длинная пауза
    gap = 0.55 if len(l["text"]) > 65 else 0.42
    if l["text"].startswith(("Проверка!", "ИИ сделает")):
        gap = 4.2
    out.append({**l, "start": round(t, 3), "end": round(t + d, 3), "dur": round(d, 3)})
    t += d + gap
    prev_scene = l["scene"]

# cues для субтитров
def chunks(txt, maxc=84):
    parts = re.split(r'(?<=[.!?…:])\s+', txt)
    res, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) + 1 > maxc:
            res.append(cur); cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur: res.append(cur)
    fin = []
    for r in res:
        if len(r) <= maxc:
            fin.append(r); continue
        bits = re.split(r'(?<=[,;—])\s+', r)
        cur = ""
        for b in bits:
            if cur and len(cur) + len(b) + 1 > maxc:
                fin.append(cur); cur = b
            else:
                cur = (cur + " " + b).strip()
        if cur: fin.append(cur)
    return fin

cues = []
for l in out:
    cs = chunks(l["text"])
    tot = sum(len(c) for c in cs)
    t0 = l["start"]
    for c in cs:
        d = l["dur"] * len(c) / tot
        cues.append({"who": l["who"], "text": c, "start": round(t0, 3), "end": round(t0 + d, 3)})
        t0 += d

os.makedirs(f"{R}/remotion/public", exist_ok=True)
json.dump({"fps": 30, "total": round(t, 2), "lines": out, "cues": cues},
          open(f"{R}/remotion/public/timing-pixar.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# SRT для Pixar-версии
def ts(x):
    h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return f"{h:02}:{m:02}:{int(s):02},{int(s*1000%1000):03}"

os.makedirs(f"{R}/subtitles", exist_ok=True)
with open(f"{R}/subtitles/ru-pixar.srt", "w", encoding="utf-8") as fh:
    for i, c in enumerate(cues, 1):
        fh.write(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n\n")

print(f"pixar: {len(out)} реплик, total {t:.1f}s = {t/60:.1f} мин, cues {len(cues)}")
# также сгенерируем обычный timing.json если его нет (чтоб не ломался Main)
if not os.path.exists(f"{R}/remotion/public/timing.json"):
    import shutil
    shutil.copy(f"{R}/remotion/public/timing-pixar.json", f"{R}/remotion/public/timing.json")
    print("скопирован в timing.json (для совместимости)")
