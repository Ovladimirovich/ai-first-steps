import { useCurrentFrame, interpolate } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS4_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  const mag = 8 + Math.sin(f/10)*2;
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Исследуй как детектив</PixarTitle>
      <div style={{position:"absolute", left:90, top:200, width:820, height:420, background:"#fff", borderRadius:28, padding:22, boxShadow:"0 18px 40px rgba(0,0,0,.14), inset 0 1px 0 #fff"}}>
        <div style={{display:"flex", gap:14, alignItems:"center"}}>
          <div style={{width:64, height:64, borderRadius:32, border:`${mag}px solid #2EE6D6`, display:"grid", placeItems:"center", fontSize:32}}>🔍</div>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:26, color:"#1B2A4A"}}>Почему небо голубое?</div>
        </div>
        <div style={{marginTop:18, display:"grid", gap:12}}>
          {[
            {src:"Учебник", col:"#E0FFF4"},
            {src:"Статья NASA", col:"#FFF6E0"},
            {src:"Видео-профессор", col:"#E0E8FF"},
          ].map((s,i)=>(
            <div key={s.src} style={{
              background:s.col, borderRadius:14, height:62, display:"flex", alignItems:"center", gap:14, padding:"0 16px",
              border:"2px solid #fff", boxShadow:"0 6px 14px rgba(0,0,0,.08)",
              opacity: interpolate(f, [d(0)+i*18, d(0)+i*18+18],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp"})
            }}>
              <div style={{width:36, height:36, borderRadius:8, background:"#1B2A4A", display:"grid", placeItems:"center", color:"#fff", fontWeight:800}}>{i+1}</div>
              <div style={{fontFamily:"Montserrat, Arial", fontWeight:700, color:"#1B2A4A"}}>{s.src}</div>
              <div style={{marginLeft:"auto", color:"#1AA89C", fontWeight:800}}>✓</div>
            </div>
          ))}
        </div>
        <div style={{marginTop:14, background:"#1B2A4A", color:"#FFD23F", borderRadius:12, padding:"10px 14px", fontFamily:"Montserrat, Arial", fontWeight:800, textAlign:"center", opacity: f> d(0)+40 ? 1:0}}>Где они расходятся? 🕵️</div>
      </div>
      <PixarCard x={960} y={220} w={870} delay={d(0)} bg="#243A66" size={27}>Попроси: <PixarHL>«Найди 3 версии и скажи где спорят»</PixarHL></PixarCard>
      {f>d(0)+18 && <PixarCard x={960} y={420} w={870} delay={d(0)+18} bg="#fff" size={24}><span style={{color:"#1B2A4A"}}>ИИ научит <b style={{color:"#FF6B6B"}}>проверять</b>, а не верить</span></PixarCard>}
      {f>d(1) && <PixarCard x={960} y={600} w={870} delay={d(1)} bg="#1f5e46" size={24}>Суперсила <PixarHL>учёного</PixarHL> — уже в 6 классе</PixarCard>}
    </>
  );
};
