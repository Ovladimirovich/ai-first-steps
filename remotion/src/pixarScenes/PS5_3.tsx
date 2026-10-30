import { useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

const SHELF = [
  { ic:"🏔️", t:"Постер Байкал", q:"сделано с ИИ" },
  { ic:"👾", t:"Игра", q:"идея моя" },
  { ic:"🎬", t:"Видео", q:"+ музыка ИИ" },
  { ic:"🏅", t:"Грамота", q:"конкурс" },
];

export const PS5_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Начни портфолио сейчас</PixarTitle>
      {/* полка */}
      <div style={{
        position:"absolute", left:90, top:190, width:1740, height:380, background:"#C9A86A", borderRadius:28,
        boxShadow:"0 22px 50px rgba(0,0,0,.18), inset 0 8px 18px rgba(255,255,255,.35)", padding:18, display:"flex", gap:16
      }}>
        {SHELF.map((s,i)=>(
          <div key={s.t} style={{
            flex:1, background:"#fff", borderRadius:20, padding:18, display:"grid", placeItems:"center", textAlign:"center",
            boxShadow:"0 10px 22px rgba(0,0,0,.14), inset 0 1px 0 #fff", border:"2px solid #fff",
            opacity: f> d(0)+i*12 ? 1:0, transform:`translateY(${f> d(0)+i*12?0:16}px)`
          }}>
            <div>
              <div style={{fontSize:56}}>{s.ic}</div>
              <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:20, color:"#1B2A4A", marginTop:8}}>{s.t}</div>
              <div style={{marginTop:6, background:"#1B2A4A", color:"#FFD23F", borderRadius:8, padding:"4px 10px", fontWeight:800, fontSize:14}}>{s.q}</div>
            </div>
          </div>
        ))}
      </div>
      <PixarCard x={90} y={640} w={1740} delay={d(0)} bg="#243A66" size={27}>Не оценки, а <PixarHL>реальные работы</PixarHL> — покажешь в колледж и на конкурс</PixarCard>
      {f>d(1) && <PixarCard x={90} y={770} w={1740} delay={d(1)} bg="#fff" size={24}><span style={{color:"#1B2A4A"}}>Домашка → <b style={{color:"#1AA89C"}}>проект для портфолио</b> 📁</span></PixarCard>}
    </>
  );
};
