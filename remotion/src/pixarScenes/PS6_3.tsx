import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS6_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number, fr=0)=> Math.round(((lines[i]?.start??0)+((lines[i]?.end??0)-(lines[i]?.start??0))*fr - sceneStart)*30);
  const pull = interpolate(f, [d(0,0.3), d(0,0.85)],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp"});
  const items:[string,string][]=[["🎓","репетитор"],["🎨","творец"],["🔍","исследователь"],["🚀","профессия"]];
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"radial-gradient(1000px 600px at 50% 35%, #FFF6E0 0%, #FFE9B8 65%, #FFDAB0 100%)"}}/>
      <PixarTitle light>Везде одно</PixarTitle>
      {items.map(([ic,t], i)=>{
        const ang=(i/4)*Math.PI*2 - Math.PI/2, r=340 - pull*46, scale=0.92+0.08*pull;
        return (
          <div key={t} style={{
            position:"absolute", left: 960 + Math.cos(ang)*r*1.55 - 95, top: 520 + Math.sin(ang)*r*0.82 - 62,
            width:190, height:124, background:"#fff", borderRadius:22, display:"grid", placeItems:"center", textAlign:"center",
            fontFamily:"Montserrat, Arial", fontWeight:800, color:"#1B2A4A", fontSize:20,
            boxShadow:"0 14px 30px rgba(0,0,0,.14), inset 0 1px 0 #fff", border:"2px solid #fff",
            transform:`scale(${scale})`
          }}>
            <div><div style={{fontSize:34}}>{ic}</div>{t}</div>
          </div>
        );
      })}
      <div style={{
        position:"absolute", left:760, top:452, width:400, height:150, borderRadius:26,
        background:"linear-gradient(180deg, #FFD23F, #FFB84D)", display:"grid", placeItems:"center", textAlign:"center",
        fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:22, color:"#0d1526",
        boxShadow:"0 18px 40px rgba(255,210,63,.45), inset 0 1px 0 rgba(255,255,255,.6)",
        opacity: pull, transform:`scale(${0.92+0.08*pull})`, border:"2px solid #fff"
      }}>
        ИИ учился<br/>на примерах →<br/>помогает <span style={{color:"#1B2A4A"}}>тебе</span>
      </div>
      {f>d(1) && <PixarCard x={90} y={780} w={1740} delay={d(1)} bg="#243A66" size={24}><PixarHL>Чит-код, но честный</PixarHL> — ты всё равно думаешь и доделываешь</PixarCard>}
    </>
  );
};
