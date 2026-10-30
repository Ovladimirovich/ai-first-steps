import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";
export const PS2_4: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"radial-gradient(900px 500px at 50% 25%, #FFF6E0 0%, #FFE9B8 62%, #FFDAB0 100%)"}}/>
      <PixarTitle light>Запомним</PixarTitle>
      <div style={{position:"absolute", left:90, top:260, width:1740, height:360, background:"#fff", borderRadius:36, boxShadow:"0 30px 70px rgba(0,0,0,.16), inset 0 1px 0 #fff", display:"grid", placeItems:"center", textAlign:"center", padding:40}}>
        <div>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:62, color:"#1B2A4A"}}>Суперсила №2</div>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:48, color:"#FF6B6B", marginTop:8}}>творишь без супернавыков</div>
          <div style={{fontFamily:"Montserrat, Arial", fontSize:22, color:"#5A3A2A", marginTop:10}}>промпт → шум → картинка / видео / музыка</div>
        </div>
      </div>
      <PixarCard x={90} y={700} w={1740} delay={d(0)} bg="#243A66" size={28}><PixarHL>Ты — автор идеи</PixarHL>, ИИ — кисти. Выбирай, а не копипасть.</PixarCard>
    </>
  );
};
