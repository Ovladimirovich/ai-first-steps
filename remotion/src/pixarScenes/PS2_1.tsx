import { useCurrentFrame, interpolate } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS2_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  const wobble = Math.sin(f/12)*4;
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Хочу, но не умею?</PixarTitle>
      <div style={{position:"absolute", left:90, top:200, width:820, height:500, background:"#fff", borderRadius:32, padding:22, boxShadow:"0 22px 50px rgba(0,0,0,.14), inset 0 1px 0 #fff", transform:`rotate(${-1+wobble*0.15}deg)`}}>
        <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:26, color:"#5A3A2A"}}>Мой скетчбук ✏️</div>
        <div style={{marginTop:16, background:"#FFF6E0", borderRadius:20, height:360, display:"grid", placeItems:"center", border:"3px dashed #D9B56A"}}>
          <div style={{textAlign:"center", opacity:0.7}}>
            <div style={{fontSize:84}}>🐱‍🚀</div>
            <div style={{fontFamily:"Montserrat, Arial", fontSize:18, color:"#5A3A2A"}}>кривой кот (но милый)</div>
          </div>
        </div>
      </div>
      <div style={{
        position:"absolute", left:980, top:200, width:850, height:500, background:"#0D1526", borderRadius:32, padding:18,
        boxShadow:"0 22px 50px rgba(0,0,0,.22)", transform:`rotate(${1-wobble*0.15}deg)`
      }}>
        <div style={{background:"#FFFDF5", borderRadius:20, height:"100%", padding:18}}>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:24, color:"#1B2A4A"}}>Промпт → <span style={{color:"#2EE6D6"}}>заказ художнику</span></div>
          <div style={{marginTop:12, background:"#0D1526", color:"#2EE6D6", borderRadius:12, padding:"12px 14px", fontFamily:"monospace", fontSize:20}}>› кот-космонавт на Луне, Pixar, 4k</div>
          <div style={{marginTop:14, background:"linear-gradient(180deg,#FFE9B8,#FFD6A0)", borderRadius:16, height:260, display:"grid", placeItems:"center", fontSize:72, boxShadow:"inset 0 8px 18px rgba(0,0,0,.08)"}}>🐱‍🚀✨</div>
        </div>
      </div>
      {f>d(1) && <PixarCard x={90} y={750} w={1740} delay={d(1)} bg="#243A66" size={28}>ИИ рисует <PixarHL>с твоих слов</PixarHL> — это <PixarHL>промпт</PixarHL></PixarCard>}
    </>
  );
};
