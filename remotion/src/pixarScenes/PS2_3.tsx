import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

const ITEMS = [
  { t:"обложка для доклада про Байкал", bg:"#E0FFF4", ic:"🏔️" },
  { t:"весёлая песня про лето, рок", bg:"#FFE9E9", ic:"🎸" },
  { t:"видео — Байкал зимой, дрон", bg:"#E0E8FF", ic:"🚁" },
  { t:"идея для игры про космос", bg:"#FFF6E0", ic:"👾" },
];

export const PS2_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Твоя обложка, твой трек</PixarTitle>
      <div style={{position:"absolute", left:90, top:190, width:1740, height:360, display:"flex", gap:18, overflow:"hidden"}}>
        {ITEMS.map((it, i)=>{
          const x = ((i*420 - f*2) % (ITEMS.length*420 + 80) + ITEMS.length*420+80) % (ITEMS.length*420+80) - 40;
          const bob = Math.sin(f/16 + i)*6;
          return (
            <div key={i} style={{
              position:"absolute", left:x, top:20+bob, width:400, height:320, background:it.bg, borderRadius:28,
              boxShadow:"0 18px 40px rgba(0,0,0,.14), inset 0 1px 0 #fff", padding:22, display:"grid", placeItems:"center", textAlign:"center",
              border:"2px solid #fff"
            }}>
              <div>
                <div style={{fontSize:56}}>{it.ic}</div>
                <div style={{fontFamily:"Montserrat, Arial", fontWeight:700, fontSize:20, color:"#1B2A4A", marginTop:8, lineHeight:1.2}}>{it.t}</div>
                <div style={{marginTop:10, fontSize:14, color:"#1AA89C", fontWeight:800}}>сделано за минуту</div>
              </div>
            </div>
          );
        })}
      </div>
      <PixarCard x={90} y={600} w={1740} delay={d(0)} bg="#243A66" size={28}>ИИ сделает <PixarHL>черновик</PixarHL> — ты выберешь лучшее и <PixarHL>доделаешь руками</PixarHL></PixarCard>
      {f>d(1) && <PixarCard x={90} y={750} w={840} delay={d(1)} bg="#fff" size={24}><span style={{color:"#1B2A4A"}}>Ты всё равно <b style={{color:"#FF6B6B"}}>автор</b> — идея твоя, ИИ — кисти 🎨</span></PixarCard>}
      {f>d(1)+10 && <PixarCard x={960} y={750} w={870} delay={d(1)+10} bg="#1f5e46" size={22}>Ускоряет в <PixarHL>10 раз</PixarHL> — успеешь и погулять</PixarCard>}
    </>
  );
};
