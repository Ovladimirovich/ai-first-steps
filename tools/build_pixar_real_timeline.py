"""Собирает реальный таймлайн Pixar из озвученных реплик.
Вход: script/lines_pixar_why_ai.json + assets/audio/voice-pixar/*.mp3
Выход: remotion/public/timing-pixar.json, subtitles/ru-pixar.srt, remotion/public/audio/voice_track-pixar.mp3
Паузы: как в build_pixar_timing.py но с реальными длительностями.
"""
import json, re, subprocess, os, sys
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def dur(f):
    o = subprocess.run([FF, '-i', f], capture_output=True, text=True).stderr
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', o)
    if not m: raise RuntimeError(f"no duration for {f}: {o[:500]}")
    h, mm, s = m.groups()
    return int(h)*3600+int(mm)*60+float(s)

lines = json.load(open(f'{R}/script/lines_pixar_why_ai.json', encoding='utf-8'))
t = 0.0
prev_scene = None
out = []
missing = []
files = []

for l in lines:
    f = f"{R}/assets/audio/voice-pixar/{l['id']}.mp3"
    if not os.path.exists(f):
        missing.append(l['id'])
        continue
    if prev_scene and l['scene'] != prev_scene:
        t += 1.1  # между сценами
    # викторинные паузы — длинные
    gap = 0.55 if len(l['text']) > 65 else 0.42
    if l['text'].startswith(('Проверка!', 'ИИ сделает')):
        gap = 4.2
    # перед сценой 0.1 +0.6? нет
    d = dur(f)
    out.append({**l, 'start': round(t, 3), 'end': round(t+d, 3), 'dur': round(d, 3)})
    files.append((f, t))
    t += d + gap
    prev_scene = l['scene']

print(f"pixar real: озвучено {len(out)}/{len(lines)}, total {t:.1f}s = {t/60:.1f} мин, missing {missing}")

# cues / srt — режем длинные реплики на куски <=84 по пунктуации, время пропорционально длине
def chunks(txt, maxc=84):
    parts = re.split(r'(?<=[.!?…:])\s+', txt)
    res, cur = [], ""
    for p in parts:
        if cur and len(cur)+len(p)+1>maxc:
            res.append(cur); cur=p
        else:
            cur=(cur+' '+p).strip()
    if cur: res.append(cur)
    fin=[]
    for r in res:
        if len(r)<=maxc: fin.append(r); continue
        bits=re.split(r'(?<=[,;—])\s+', r)
        cur=""
        for b in bits:
            if cur and len(cur)+len(b)+1>maxc: fin.append(cur); cur=b
            else: cur=(cur+' '+b).strip()
        if cur: fin.append(cur)
    return fin

cues=[]
for l in out:
    cs=chunks(l['text'])
    tot=sum(len(c) for c in cs)
    t0=l['start']
    for c in cs:
        d=l['dur']*len(c)/tot
        cues.append({'who':l['who'],'text':c,'start':round(t0,3),'end':round(t0+d,3)})
        t0+=d

os.makedirs(f'{R}/remotion/public', exist_ok=True)
os.makedirs(f'{R}/remotion/public/audio', exist_ok=True)
json.dump({'fps':30,'total':round(t,2),'lines':out,'cues':cues}, open(f'{R}/remotion/public/timing-pixar.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"  cues {len(cues)} -> timing-pixar.json")

def ts(x):
    h=int(x//3600); m=int(x%3600//60); s=x%60
    return f"{h:02}:{m:02}:{int(s):02},{int(s*1000%1000):03}"

os.makedirs(f'{R}/subtitles', exist_ok=True)
with open(f'{R}/subtitles/ru-pixar.srt','w',encoding='utf-8') as fh:
    for i,l in enumerate(cues,1):
        fh.write(f"{i}\n{ts(l['start'])} --> {ts(l['end'])}\n{l['text']}\n\n")
print(f"  srt {len(cues)} cues")

# voice_track-pixar.mp3 — склейка с adelay + amix + loudnorm
if files:
    inputs = sum([['-i', f] for f,_ in files], [])
    fc = ''.join(f"[{i}:a]adelay={int(st*1000)}|{int(st*1000)}[a{i}];" for i,(_,st) in enumerate(files))
    fc += ''.join(f'[a{i}]' for i in range(len(files))) + f'amix=inputs={len(files)}:normalize=0,loudnorm=I=-16:TP=-1.5[o]'
    out_mp3 = f'{R}/remotion/public/audio/voice_track-pixar.mp3'
    print(f"  building {out_mp3} from {len(files)} clips...")
    subprocess.run([FF,'-y','-v','error',*inputs,'-filter_complex',fc,'-map','[o]',out_mp3], check=True)
    print(f"  done {out_mp3} ({os.path.getsize(out_mp3)/1024/1024:.2f} MB)")
else:
    print("  no files for voice_track")

# также обновим timing.json для совместимости если нужно? Нет — оставляем оригинальный.
