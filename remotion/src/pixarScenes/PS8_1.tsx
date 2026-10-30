import { useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS8_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number, fr=0)=> Math.round(((lines[i]?.start??0)+((lines[i]?.end??0)-(lines[i]?.start??0))*fr - sceneStart)*30);
  const items:[string,string,number][]=[
    ["1","Репетитор — объясняет твоими словами",0.08],
    ["2","Творец — промпт → картинка/музыка",0.30],
    ["3","Исследователь — идеи → план → код",0.56],
    ["4","Профессия — портфолио уже сейчас",0.78],
  ];
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Повторим за 10 секунд</PixarTitle>
      {items.map(([n,t,fr])=>(
        <div key={n} style={{
          position:"absolute", left:90, top: 210 + Number(n)*140 - 40, width:1740, background:"#fff",
          borderRadius:22, padding:"18px 24px", display:"flex", alignItems:"center", gap:18,
          boxShadow:"0 14px 30px rgba(0,0,0,.14), inset 0 1px 0 #fff", border:"2px solid #fff",
          opacity: f> d(0,fr) ? 1:0, transform:`translateY(${f> d(0,fr)?0:18}px)`
        }}>
          <div style={{width:48, height:48, borderRadius:14, background:"linear-gradient(180deg, #FFD23F, #FFB84D)", display:"grid", placeItems:"center", fontWeight:800, color:"#0d1526", fontSize:22, boxShadow:"0 6px 14px rgba(255,210,63,.5)"}}>{n}</div>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:700, fontSize:26, color:"#1B2A4A"}}>{t}</div>
        </div>
      ))}
      {f> d(1) && <PixarCard x={90} y={800} w={1740} delay={d(1)} bg="#1f5e46" size={24}>4 причины дружить с ИИ <PixarHL>уже в школе</PixarHL> 🎒</PixarCard>}
    </>
  );
};
