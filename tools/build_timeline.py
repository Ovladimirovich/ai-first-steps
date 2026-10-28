"""Собирает таймлайн из озвученных реплик.
Вход: script/lines.json + assets/audio/voice/*.mp3
Выход: remotion/public/timing.json, subtitles/ru.srt, assets/audio/voice_track.mp3
Паузы: 0.45с внутри быстрого диалога, 0.6с после длинных реплик, 1.2с между сценами, +0.8с перед «Миллиарды».
"""
import json,re,subprocess,os,sys,imageio_ffmpeg
FF=imageio_ffmpeg.get_ffmpeg_exe(); R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def dur(f):
    o=subprocess.run([FF,'-i',f],capture_output=True,text=True).stderr
    h,m,s=re.search(r'Duration: (\d+):(\d+):([\d.]+)',o).groups(); return int(h)*3600+int(m)*60+float(s)
lines=json.load(open(f'{R}/script/lines.json'))
t=0.0; prev_scene=None; out=[]; missing=[]; files=[]
for l in lines:
    f=f"{R}/assets/audio/voice/{l['id']}.mp3"
    if not os.path.exists(f): missing.append(l['id']); continue
    if prev_scene and l['scene']!=prev_scene: t+=1.2
    if l['text'].startswith('Миллиарды'): t+=0.8
    d=dur(f); out.append({**l,'start':round(t,3),'end':round(t+d,3),'dur':round(d,3)}); files.append((f,t))
    gap=0.6 if len(l['text'])>60 else 0.45
    if l['text'].startswith(('Проверка!','Вторая проверка!')): gap=4.5  # таймер викторины
    t+=d+gap; prev_scene=l['scene']
# субтитры: режем длинные реплики на куски <= 84 символов по знакам препинания, время — пропорционально длине
import textwrap
def chunks(txt,maxc=84):
    parts=re.split(r'(?<=[.!?…:])\s+',txt); res=[]; cur=''
    for p in parts:
        if cur and len(cur)+len(p)+1>maxc: res.append(cur); cur=p
        else: cur=(cur+' '+p).strip()
    if cur: res.append(cur)
    fin=[]
    for r in res:
        if len(r)<=maxc: fin.append(r); continue
        # длинное предложение: режем по запятым/тире, набирая куски до maxc
        bits=re.split(r'(?<=[,;—])\s+',r); cur=''
        for b in bits:
            if cur and len(cur)+len(b)+1>maxc: fin.append(cur); cur=b
            else: cur=(cur+' '+b).strip()
        if cur: fin.append(cur)
    return fin
cues=[]
for l in out:
    cs=chunks(l['text']); tot=sum(len(c) for c in cs); t0=l['start']
    for c in cs:
        d=l['dur']*len(c)/tot; cues.append({'who':l['who'],'text':c,'start':round(t0,3),'end':round(t0+d,3)}); t0+=d
json.dump({'fps':30,'total':round(t,2),'lines':out,'cues':cues},open(f'{R}/remotion/public/timing.json','w'),ensure_ascii=False,indent=1)
# SRT
def ts(x): h=int(x//3600);m=int(x%3600//60);s=x%60; return f"{h:02}:{m:02}:{int(s):02},{int(s*1000%1000):03}"
with open(f'{R}/subtitles/ru.srt','w') as fh:
    for i,l in enumerate(cues,1): fh.write(f"{i}\n{ts(l['start'])} --> {ts(l['end'])}\n{l['text']}\n\n")
# voice track: place each clip at its offset
if files:
    inputs=sum([['-i',f] for f,_ in files],[])
    fc=''.join(f"[{i}:a]adelay={int(st*1000)}|{int(st*1000)}[a{i}];" for i,(_,st) in enumerate(files))
    fc+=''.join(f'[a{i}]' for i in range(len(files)))+f'amix=inputs={len(files)}:normalize=0,loudnorm=I=-16:TP=-1.5[o]'
    subprocess.run([FF,'-y','-v','error',*inputs,'-filter_complex',fc,'-map','[o]',f'{R}/remotion/public/audio/voice_track.mp3'],check=True)
print(f"озвучено {len(out)}/{len(lines)} реплик, длительность трека {t/60:.1f} мин; не озвучено: {len(missing)}")
