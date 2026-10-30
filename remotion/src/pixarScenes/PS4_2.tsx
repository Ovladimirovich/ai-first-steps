import { useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

const STEPS = ["1. Гипотеза","2. Опыт","3. Фото/замер","4. Вывод + постер"];

export const PS4_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Разложит по шагам</PixarTitle>
      <div style={{position:"absolute", left:90, top:200, width:1100, background:"#fff", borderRadius:28, padding:22, boxShadow:"0 18px 40px rgba(0,0,0,.14)"}}>
        <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:26, color:"#1B2A4A", marginBottom:14}}>План на неделю 📅</div>
        <div style={{display:"flex", gap:14}}>
          {STEPS.map((s,i)=>(
            <div key={s} style={{
              flex:1, background: f> d(0)+i*12 ? "#2EE6D6" : "#E8EEF6", borderRadius:16, height:110, display:"grid", placeItems:"center",
              fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:18, color: f> d(0)+i*12 ? "#0d1526":"#5A7A9A",
              boxShadow: f> d(0)+i*12 ? "0 10px 22px rgba(46,230,214,.4)" : "none", border:"2px solid #fff",
              transform: f> d(0)+i*12 ? "scale(1.02)" : "none"
            }}>{s}</div>
          ))}
        </div>
        <div style={{marginTop:16, display:"flex", gap:10, alignItems:"center", fontFamily:"Montserrat, Arial", fontSize:18, color:"#5A3A2A"}}>
          <span style={{background:"#FFE9B8", borderRadius:8, padding:"6px 10px", fontWeight:800}}>🧾 Что купить</span>
          <span style={{background:"#E0FFF4", borderRadius:8, padding:"6px 10px", fontWeight:800}}>📏 Как измерить</span>
          <span style={{background:"#FFE9E9", borderRadius:8, padding:"6px 10px", fontWeight:800}}>💻 Код подскажет</span>
        </div>
      </div>
      <PixarCard x={1240} y={220} w={590} delay={d(0)} bg="#243A66" size={26}>ИИ — твой <PixarHL>менеджер проекта</PixarHL></PixarCard>
      {f>d(1) && <PixarCard x={1240} y={420} w={590} delay={d(1)} bg="#fff" size={24}><span style={{color:"#1B2A4A"}}>Даже <b>код для Arduino</b> объяснит<br/>строка за строкой</span></PixarCard>}
      {f>d(1)+10 && <PixarCard x={1240} y={620} w={590} delay={d(1)+10} bg="#1f5e46" size={22}>Попроси: <PixarHL>«Объясни как для новичка»</PixarHL></PixarCard>}
    </>
  );
};
