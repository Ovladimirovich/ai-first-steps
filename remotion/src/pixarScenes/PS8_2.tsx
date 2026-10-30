import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import { Cat } from "../components/Cat";
import type { SceneProps } from "../scenes";

export const PS8_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  const end = Math.round(((lines[lines.length-1]?.end??0)-sceneStart)*30);
  const dogX = interpolate(f, [d(1), d(1)+100], [-220, 1380], {extrapolateRight:"clamp"});
  const credO = interpolate(f, [end+18, end+46],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp"});
  const credits = [
    "Факты актуальны на октябрь 2026",
    "Pixar-версия: «Зачем ИИ школьнику» — проект с Битом и Машей",
    "Инструменты: Remotion · Blender-концепт · TTS · ffmpeg",
    "Алиса, GigaChat, Kandinsky — товарные знаки их владельцев",
    "Персонажи и фоны — Pixar-стилизация · СС BY-NC 4.0",
  ];
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 62%, #FFDAB0 100%)"}}/>
      <PixarTitle light>Попробуй сам — челлендж</PixarTitle>
      <div style={{
        position:"absolute", left:90, top:180, width:1100, background:"#fff", borderRadius:28, padding:22,
        boxShadow:"0 18px 40px rgba(0,0,0,.14), inset 0 1px 0 #fff", border:"2px solid #fff"
      }}>
        <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:26, color:"#1B2A4A"}}>Челлендж на неделю 📋</div>
        <div style={{marginTop:14, display:"grid", gap:10}}>
          {[
            "Выбери 1 тему из домашки",
            "Попроси ИИ объяснить 3 способами",
            "Сделай 1 постер и покажи учителю",
          ].map((t,i)=>(
            <div key={t} style={{
              background: i===0?"#E0FFF4": i===1?"#FFF6E0":"#FFE9E9", borderRadius:14, height:56,
              display:"flex", alignItems:"center", gap:12, padding:"0 16px",
              border:"2px solid #fff", boxShadow:"0 6px 14px rgba(0,0,0,.08)",
              opacity: f> d(0)+i*14 ? 1:0.45
            }}>
              <div style={{width:28, height:28, borderRadius:8, border:"3px solid #1B2A4A", background: f> d(0)+24+i*14 ? "#2EE6D6":"#fff"}}/>
              <div style={{fontFamily:"Montserrat, Arial", fontWeight:700, color:"#1B2A4A"}}>{t}</div>
            </div>
          ))}
        </div>
        <div style={{marginTop:14, display:"flex", gap:10}}>
          <span style={{background:"#1B2A4A", color:"#FFD23F", borderRadius:10, padding:"8px 14px", fontWeight:800, fontSize:16}}>Алиса</span>
          <span style={{background:"#1B2A4A", color:"#2EE6D6", borderRadius:10, padding:"8px 14px", fontWeight:800, fontSize:16}}>GigaChat</span>
          <span style={{background:"#fff", border:"2px solid #1B2A4A", borderRadius:10, padding:"6px 12px", fontWeight:800, fontSize:14}}>спроси у родителей 13+</span>
        </div>
      </div>

      {f> d(1) && <Cat style={{position:"absolute", left:90, top:650, width:300, height:300, borderRadius:24, boxShadow:"0 18px 40px rgba(0,0,0,.14)", opacity: interpolate(f, [d(2), d(2)+40],[0.35,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp"})}}/>}
      {f>d(2) && <PixarCard x={420} y={680} w={760} delay={d(2)} bg="#1f5e46" size={26}>Сделай своего — <PixarHL>теперь ты знаешь как</PixarHL> ✨</PixarCard>}

      {/* Пиксель пробегает */}
      <div style={{position:"absolute", left:dogX, top:860, width:200, filter:"drop-shadow(0 12px 16px rgba(0,0,0,.22))", fontSize:72}}>🐕</div>

      {/* титры Pixar */}
      <div style={{position:"absolute", inset:0, background:"#FFF6E0", opacity: credO, display:"grid", placeItems:"center"}}>
        <div style={{textAlign:"center", padding:40}}>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:72, color:"#1B2A4A"}}>Зачем ИИ <span style={{color:"#FF6B6B"}}>школьнику</span>?</div>
          <div style={{fontFamily:"Montserrat, Arial", fontSize:22, color:"#5A3A2A", marginTop:8}}>Pixar-версия · 5–8 класс</div>
          <div style={{marginTop:28, display:"grid", gap:8}}>
            {credits.map((c,i)=>(
              <div key={i} style={{
                fontFamily:"Montserrat, Arial", fontSize:20, color:"#1B2A4A", opacity: interpolate(f, [end+40+i*12, end+60+i*12],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp"}),
                background:"#fff", borderRadius:12, padding:"8px 18px", boxShadow:"0 6px 14px rgba(0,0,0,.08)", display:"inline-block"
              }}>{c}</div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
};
