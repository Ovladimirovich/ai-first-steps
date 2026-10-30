import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS5_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  const drift = interpolate(f, [0,300], [0,-20], {extrapolateRight:"clamp"});
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #E0F7FF 0%, #FFF6E0 55%, #FFE9B8 100%)"}}/>
      {/* город будущего — силуэты */}
      <div style={{
        position:"absolute", left:0, right:0, bottom:300, height:260, background:"linear-gradient(180deg, transparent, rgba(27,42,74,.08))",
        display:"flex", alignItems:"flex-end", justifyContent:"center", gap:8, padding:"0 40px", transform:`translateX(${drift}px)`
      }}>
        {[
          {h:120, w:90, c:"#B8D8FF"}, {h:180, w:70, c:"#FFD6A0"}, {h:140, w:110, c:"#C8FFE0"},
          {h:200, w:80, c:"#FFC8C8"}, {h:100, w:100, c:"#E0E0FF"}, {h:160, w:90, c:"#FFF0A0"},
        ].map((b,i)=>(
          <div key={i} style={{width:b.w, height:b.h, background:b.c, borderRadius:"14px 14px 0 0", border:"2px solid #fff", boxShadow:"0 10px 22px rgba(0,0,0,.12)", position:"relative"}}>
            <div style={{position:"absolute", left:8, top:12, right:8, bottom:8, display:"grid", gridTemplateColumns:"1fr 1fr", gap:6}}>
              {Array.from({length:6}).map((_,k)=>(<div key={k} style={{background:"rgba(255,255,255,.9)", borderRadius:4}}/>))}
            </div>
          </div>
        ))}
      </div>
      {/* дроны */}
      <div style={{position:"absolute", left: 300 + Math.sin(f/18)*12, top: 160, fontSize:44, filter:"drop-shadow(0 8px 12px rgba(0,0,0,.18))"}}>🛸</div>
      <div style={{position:"absolute", left: 1100 + Math.cos(f/14)*10, top: 190, fontSize:36}}>🚁</div>

      <PixarTitle light>Кем ты будешь?</PixarTitle>
      <PixarCard x={90} y={640} w={840} delay={d(0)} bg="#243A66" size={30}><PixarHL>ИИ не заменит человека</PixarHL></PixarCard>
      {f>d(1) && <PixarCard x={960} y={640} w={870} delay={d(1)} bg="#1f5e46" size={28}>Но <PixarHL>человек с ИИ</PixarHL> заменит<br/>человека без ИИ</PixarCard>}
      {f>d(1)+10 && <PixarCard x={90} y={800} w={1740} delay={d(1)+10} bg="#fff" size={22}><span style={{color:"#1B2A4A"}}>Будь тем, кто <b style={{color:"#FF6B6B"}}>дружит с ИИ</b></span></PixarCard>}
    </>
  );
};
