import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS1_4: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"radial-gradient(1000px 500px at 50% 20%, #FFF6E0 0%, #FFE9B8 60%, #FFDAB0 100%)"}}/>
      <PixarTitle light>Запомним</PixarTitle>
      <div style={{
        position:"absolute", left:90, top:260, width:1740, height:420, background:"#fff",
        borderRadius:36, boxShadow:"0 30px 70px rgba(0,0,0,.18), inset 0 1px 0 #fff",
        display:"grid", placeItems:"center", textAlign:"center", padding:40
      }}>
        <div>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:72, color:"#1B2A4A", lineHeight:1}}>Суперсила №1</div>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:54, color:"#1AA89C", marginTop:12}}>личный репетитор 24/7</div>
          <div style={{fontFamily:"Montserrat, Arial", fontSize:26, color:"#5A3A2A", marginTop:12}}>объясняет твоими словами · без оценок · сколько угодно раз</div>
        </div>
      </div>
      <PixarCard x={90} y={740} w={1740} delay={d(0)} bg="#243A66" size={28}><PixarHL>Попроси</PixarHL> как для друга / через мем / через игру — он <PixarHL>подстроится</PixarHL></PixarCard>
    </>
  );
};
