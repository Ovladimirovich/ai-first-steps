import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS3_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const q = lines[0], a = lines[1];
  const t0 = q ? (q.end - sceneStart)*30 : 0, t1 = a ? (a.start - sceneStart)*30 : t0+130;
  const left = Math.max(0, Math.ceil(interpolate(f, [t0, t1], [5,0], {extrapolateLeft:"clamp", extrapolateRight:"clamp"})));
  const revealed = f>=t1;
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>⏱ Проверка №1</PixarTitle>
      <div style={{position:"absolute", left:90, top:200, width:1740, background:"#fff", borderRadius:28, padding:22, boxShadow:"0 18px 40px rgba(0,0,0,.14)", display:"flex", alignItems:"center", gap:18}}>
        <div style={{fontSize:56}}>🤔</div>
        <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:32, color:"#1B2A4A"}}>Если ИИ написал сочинение и ты сдал как своё — это честно?</div>
      </div>
      <div style={{position:"absolute", left:90, top:380, display:"flex", gap:32, alignItems:"center"}}>
        {["ДА","НЕТ"].map(o=>(
          <div key={o} style={{
            width:320, height:150, borderRadius:28, display:"grid", placeItems:"center",
            fontSize:62, fontWeight:800, fontFamily:"Montserrat, Arial",
            background: revealed && o==="НЕТ" ? "#2EE6D6" : "#243A66",
            color: revealed && o==="НЕТ" ? "#0d1526":"#fff",
            transform: revealed && o==="НЕТ" ? "scale(1.06)" : "none",
            boxShadow: revealed && o==="НЕТ" ? "0 18px 40px rgba(46,230,214,.5)" : "0 10px 28px rgba(0,0,0,.14)",
            border:"3px solid rgba(255,255,255,.6)"
          }}>{o}</div>
        ))}
        {!revealed && f>t0 && <div style={{width:130, height:130, borderRadius:65, border:"10px solid #FFD23F", display:"grid", placeItems:"center", fontSize:64, fontWeight:800, color:"#FFD23F", background:"#fff"}}>{left}</div>}
      </div>
      {revealed && <PixarCard x={90} y={640} w={1740} delay={t1} bg="#1f5e46" size={28}>Нет! Это как выдать <PixarHL>чужой рисунок за свой</PixarHL>. Указывай: <PixarHL>сделано с ИИ</PixarHL></PixarCard>}
      {revealed && <PixarCard x={90} y={780} w={1740} delay={t1+12} bg="#243A66" size={24}>ИИ — <PixarHL>помощник</PixarHL>, а не автор. Идея — твоя.</PixarCard>}
    </>
  );
};
