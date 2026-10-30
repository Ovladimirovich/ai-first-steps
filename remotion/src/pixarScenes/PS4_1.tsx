import { useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

const CARDS = [
  { ic:"🤖", t:"Робот-поливалка", bg:"#E0FFF4" },
  { ic:"👾", t:"Игра про космос", bg:"#FFF6E0" },
  { ic:"🍦", t:"Почему тает мороженое?", bg:"#FFE9E9" },
];

export const PS4_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Где брать идеи?</PixarTitle>
      <div style={{position:"absolute", left:90, top:200, width:1740, display:"flex", gap:20}}>
        {CARDS.map((c,i)=>(
          <div key={c.t} style={{
            flex:1, background:c.bg, borderRadius:28, height:360, display:"grid", placeItems:"center", textAlign:"center", padding:22,
            boxShadow:"0 18px 40px rgba(0,0,0,.14), inset 0 1px 0 #fff", border:"2px solid #fff",
            opacity: f> d(0)+i*14 ? 1:0, transform:`translateY(${f> d(0)+i*14?0:18}px)`
          }}>
            <div>
              <div style={{fontSize:64}}>{c.ic}</div>
              <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:22, color:"#1B2A4A", marginTop:8}}>{c.t}</div>
              <div style={{marginTop:8, fontSize:14, color:"#1AA89C", fontWeight:800}}>идея за минуту</div>
            </div>
          </div>
        ))}
      </div>
      <PixarCard x={90} y={640} w={1740} delay={d(1)} bg="#243A66" size={26}>Попроси: <PixarHL>«Дай 10 идей для 6 класса про экологию, без дорогих деталей»</PixarHL></PixarCard>
      {f>d(1)+12 && <PixarCard x={90} y={780} w={1740} delay={d(1)+12} bg="#fff" size={22}><span style={{color:"#1B2A4A"}}>ИИ — <b style={{color:"#FF6B6B"}}>генератор идей</b>, а не готовых ответов</span></PixarCard>}
    </>
  );
};
