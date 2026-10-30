import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import { Cat } from "../components/Cat";
import type { SceneProps } from "../scenes";

const MiniCat: React.FC<{ wave:number; glitch?:boolean }> = ({ wave, glitch }) => (
  <div style={{width:160, height:160, background:"#000", borderRadius:16, overflow:"hidden", position:"relative", outline: glitch?"4px solid #FF6B6B":"none"}}>
    <Cat style={{width:"100%", height:"100%", display:"block", filter: glitch? "hue-rotate(90deg)":"none"}}/>
    <div style={{position:"absolute", left:14, top: 64 - wave*10, width:28, height:10, background:"#F2A65A", borderRadius:6, transform:`rotate(${-18*wave}deg)`, opacity: glitch?0.9:0.85}}/>
    {glitch && <div style={{position:"absolute", left:10, top:80, width:22, height:28, background:"#7AD17A", borderRadius:8, transform:"rotate(18deg)"}}/>}
  </div>
);

export const PS6_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number, fr=0)=> Math.round(((lines[i]?.start??0)+((lines[i]?.end??0)-(lines[i]?.start??0))*fr - sceneStart)*30);
  const glitchOn = f> d(0,0.55) && f< d(1,0.4);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Где подвох?</PixarTitle>
      <div style={{
        position:"absolute", left:90, top:210, width:1740, height:260, background:"#111", borderRadius:20,
        borderTop:"18px dashed #444", borderBottom:"18px dashed #444", display:"flex", gap:14, padding:"16px 18px", overflow:"hidden",
        boxShadow:"0 18px 40px rgba(0,0,0,.18)"
      }}>
        {Array.from({length:9}).map((_,i)=>{
          const idx=Math.floor(f/5)+i, wave=(Math.sin(idx*0.6)+1)/2, glitch= glitchOn && (idx%7===3);
          return <MiniCat key={i} wave={wave} glitch={glitch}/>;
        })}
      </div>
      <PixarCard x={90} y={540} w={1740} delay={d(0)} bg="#243A66" size={26}>ИИ иногда <PixarHL>уверенно врёт</PixarHL> — это <PixarHL>галлюцинация</PixarHL></PixarCard>
      {f> d(1) && <PixarCard x={90} y={700} w={1740} delay={d(1)} bg="#fff" size={24}><span style={{color:"#1B2A4A"}}>И видео пока с <b style={{color:"#FF6B6B"}}>3 лапами</b> — проверяй! <span style={{opacity:0.6}}>👀</span></span></PixarCard>}
    </>
  );
};
