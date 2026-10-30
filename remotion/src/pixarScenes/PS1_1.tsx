import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS1_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  const shake = Math.sin(f*0.6)*2;
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      {/* доска Pixar */}
      <div style={{
        position:"absolute", left:90, top:170, width:1100, height:520,
        background:"#2B4A3A", borderRadius:28, border:"14px solid #8B6A3A",
        boxShadow:"0 30px 60px rgba(0,0,0,.22), inset 0 8px 18px rgba(255,255,255,.18)",
        padding:28, overflow:"hidden"
      }}>
        <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:44, color:"#fff", opacity:0.95}}>Фотосинтез = ...</div>
        <div style={{marginTop:22, height:10, background:"rgba(255,255,255,.22)", borderRadius:6, width:"78%"}}/>
        <div style={{marginTop:14, height:10, background:"rgba(255,255,255,.18)", borderRadius:6, width:"54%"}}/>
        <div style={{position:"absolute", right:60, top:60, fontSize:86, transform:`rotate(${shake}deg)`}}>😵‍💫</div>
        <div style={{position:"absolute", left:40, right:40, bottom:30, display:"flex", gap:14}}>
          {["???","???","???"].map((t,i)=>(
            <div key={i} style={{
              flex:1, background:"rgba(255,255,255,.12)", borderRadius:16, height:78,
              display:"grid", placeItems:"center", color:"#FFD23F", fontWeight:800, fontSize:28,
              opacity: interpolate(f, [20+i*12, 45+i*12],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp"})
            }}>{t}</div>
          ))}
        </div>
      </div>
      <PixarTitle light>Не понял на уроке?</PixarTitle>
      <PixarCard x={1240} y={200} w={600} delay={d(0)} bg="#243A66" size={30}>Учитель быстро, <PixarHL>спросить стесняешься?</PixarHL></PixarCard>
      {f>d(2) && <PixarCard x={1240} y={420} w={600} delay={d(2)} bg="#fff" size={26}><span style={{color:"#1B2A4A"}}>ИИ — репетитор, который <b style={{color:"#FF6B6B"}}>не ставит двоек</b></span></PixarCard>}
      {f>d(2)+18 && <PixarCard x={1240} y={620} w={600} delay={d(2)+18} bg="#1f5e46" size={26}>Объяснит <PixarHL>100 раз</PixarHL> твоими словами</PixarCard>}
    </>
  );
};
